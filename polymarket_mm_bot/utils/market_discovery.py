"""
Market Discovery Module
Automatically fetches and filters high-volume markets from Polymarket API
"""
import aiohttp
import asyncio
import json
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from decimal import Decimal

logger = logging.getLogger(__name__)

GAMMA_API_URL = "https://gamma-api.polymarket.com/markets"


@dataclass
class DiscoveredMarket:
    """Represents a discovered market from the API"""
    question: str
    condition_id: str
    yes_token_id: str
    no_token_id: str
    volume: float
    liquidity: float
    spread: float  # Best ask - best bid
    yes_price: float
    no_price: float

    @property
    def short_name(self) -> str:
        """Generate a short name for the market (max 15 chars)"""
        # Take first few words and abbreviate
        words = self.question.replace("?", "").split()[:3]
        short = " ".join(words)
        if len(short) > 12:
            short = short[:12] + ".."
        return short


async def fetch_markets(
    min_volume: float = 100000,
    max_markets: int = 20,
    exclude_closed: bool = True,
    min_liquidity: float = 1000,  # Lowered - Polymarket liquidity values are smaller
    max_spread: float = 0.20,  # 20% max spread
) -> List[DiscoveredMarket]:
    """
    Fetch high-volume markets from Polymarket API.

    Args:
        min_volume: Minimum trading volume in USD
        max_markets: Maximum number of markets to return
        exclude_closed: Whether to exclude closed markets
        min_liquidity: Minimum liquidity requirement
        max_spread: Maximum bid-ask spread (0.20 = 20%)

    Returns:
        List of DiscoveredMarket objects sorted by volume
    """
    markets = []

    try:
        async with aiohttp.ClientSession() as session:
            params = {
                "closed": "false" if exclude_closed else "true",
                "limit": 100,  # Fetch more to filter
            }

            logger.info(f"Fetching markets from {GAMMA_API_URL}...")
            async with session.get(GAMMA_API_URL, params=params) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch markets: HTTP {response.status}")
                    return []

                data = await response.json()
                logger.info(f"Received {len(data)} markets from API")

                for market in data:
                    try:
                        # Skip if not accepting orders
                        if not market.get("acceptingOrders", False):
                            continue

                        # Extract token IDs - API returns JSON string, not list
                        tokens_raw = market.get("clobTokenIds", "[]")
                        if isinstance(tokens_raw, str):
                            tokens = json.loads(tokens_raw)
                        else:
                            tokens = tokens_raw

                        if not tokens or len(tokens) < 2:
                            continue

                        yes_token = tokens[0]
                        no_token = tokens[1]

                        # Get volume and liquidity - try multiple fields
                        volume = float(market.get("volumeNum", 0) or market.get("volume", 0) or 0)
                        liquidity = float(market.get("liquidityNum", 0) or market.get("liquidity", 0) or 0)

                        # Skip low volume markets
                        if volume < min_volume:
                            continue

                        # Skip low liquidity markets (but be lenient)
                        if liquidity < min_liquidity:
                            continue

                        # Get prices - API returns JSON string, not list
                        outcome_prices_raw = market.get("outcomePrices", '["0.5", "0.5"]')
                        if isinstance(outcome_prices_raw, str):
                            outcome_prices = json.loads(outcome_prices_raw)
                        else:
                            outcome_prices = outcome_prices_raw

                        if outcome_prices and len(outcome_prices) >= 2:
                            yes_price = float(outcome_prices[0])
                            no_price = float(outcome_prices[1])
                        else:
                            yes_price = 0.5
                            no_price = 0.5

                        # Get spread from API if available
                        spread = market.get("spread", None)
                        if spread is None:
                            # Calculate from best bid/ask if available
                            best_bid = float(market.get("bestBid", 0) or 0)
                            best_ask = float(market.get("bestAsk", 1) or 1)
                            spread = best_ask - best_bid if best_bid and best_ask else 0.05
                        else:
                            spread = float(spread) if spread else 0.05

                        # Skip very wide spread markets
                        if spread > max_spread:
                            continue

                        discovered = DiscoveredMarket(
                            question=market.get("question", "Unknown"),
                            condition_id=market.get("conditionId", ""),
                            yes_token_id=yes_token,
                            no_token_id=no_token,
                            volume=volume,
                            liquidity=liquidity,
                            spread=spread,
                            yes_price=yes_price,
                            no_price=no_price,
                        )
                        markets.append(discovered)

                    except Exception as e:
                        logger.debug(f"Error parsing market: {e}")
                        continue

                logger.info(f"Found {len(markets)} markets meeting criteria")

    except Exception as e:
        logger.error(f"Error fetching markets: {e}")
        import traceback
        traceback.print_exc()
        return []

    # Sort by volume descending
    markets.sort(key=lambda m: m.volume, reverse=True)

    # Return top N
    return markets[:max_markets]


async def generate_pairs_dict(
    min_volume: float = 100000,
    max_pairs: int = 10,
    include_both_sides: bool = True,
) -> Dict[str, str]:
    """
    Generate a MARKETS dict for the bot with highest volume pairs.

    Args:
        min_volume: Minimum volume filter
        max_pairs: Maximum number of market pairs (YES/NO count as 1 pair)
        include_both_sides: Whether to include both YES and NO tokens

    Returns:
        Dict mapping token_id -> short alias
    """
    markets = await fetch_markets(
        min_volume=min_volume,
        max_markets=max_pairs,
    )

    pairs = {}

    for market in markets:
        # Create short aliases
        base_name = market.short_name

        if include_both_sides:
            pairs[market.yes_token_id] = f"{base_name} Y"
            pairs[market.no_token_id] = f"{base_name} N"
        else:
            # Just include YES side
            pairs[market.yes_token_id] = base_name

    return pairs


async def print_market_summary(markets: List[DiscoveredMarket]):
    """Print a nice summary of discovered markets"""
    print("\n" + "="*80)
    print("🔍 DISCOVERED HIGH-VOLUME MARKETS")
    print("="*80)

    for i, m in enumerate(markets, 1):
        vol_str = f"${m.volume/1_000_000:.1f}M" if m.volume >= 1_000_000 else f"${m.volume/1_000:.0f}K"
        liq_str = f"${m.liquidity/1_000:.0f}K"

        print(f"\n{i:2d}. {m.question[:60]}")
        print(f"    📊 Volume: {vol_str} | 💧 Liquidity: {liq_str} | 📈 YES: {m.yes_price:.1%}")
        print(f"    🎫 YES: {m.yes_token_id[:20]}...")
        print(f"    🎫 NO:  {m.no_token_id[:20]}...")

    print("\n" + "="*80)


# Convenience function for one-liner usage
async def discover_top_markets(count: int = 10, min_vol: float = 100000) -> Dict[str, str]:
    """
    Quick function to discover top markets and return as MARKETS dict.

    Usage:
        MARKETS = asyncio.run(discover_top_markets(10))
    """
    return await generate_pairs_dict(min_volume=min_vol, max_pairs=count)


if __name__ == "__main__":
    # Test the discovery
    async def main():
        print("🔎 Fetching high-volume markets...")
        markets = await fetch_markets(min_volume=50000, max_markets=15)
        await print_market_summary(markets)

        print("\n📝 Generated MARKETS dict:")
        pairs = await generate_pairs_dict(max_pairs=10)
        for token_id, alias in pairs.items():
            print(f'    "{token_id}": "{alias}",')

    asyncio.run(main())
