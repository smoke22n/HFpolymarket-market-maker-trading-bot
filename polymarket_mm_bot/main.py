#!/usr/bin/env python3
"""
Main entry point for Polymarket Market Maker Bot
"""
import asyncio
import logging
import argparse
import sys
from typing import Dict, Any
from decimal import Decimal

from .api.client import PolymarketRestClient, PolymarketWsClient, Credentials
from .api.connection_manager import ConnectionManager
from .config.settings import load_config
from .market_data.order_book_engine import MarketDataIngestionEngine
from .strategies.hfmm_strategy import HFMStrategy, OrderBatcher
from .utils.position_manager import PositionManager
from .utils.order_manager import OrderManager
from .utils.risk_manager import RiskManager
from .utils.dry_run import DryRunMode
from .utils.simulation_engine import SimulationEngine
from .utils.config_manager import config_manager
from .utils.market_discovery import fetch_markets, generate_pairs_dict, print_market_summary
import time


async def refresh_markets_task(
    market_data_engine,
    order_manager,
    position_manager,
    current_markets: Dict[str, str],
    refresh_interval: int = 3600,  # 1 hour default
    min_volume: float = 100000,
    max_pairs: int = 10,
    logger=None
):
    """
    Background task to refresh markets periodically.
    Cancels orders for markets that no longer meet criteria.
    """
    while True:
        await asyncio.sleep(refresh_interval)

        try:
            logger.info("🔄 Refreshing market list...")

            # Fetch new high-volume markets
            new_discovered = await fetch_markets(
                min_volume=min_volume,
                max_markets=max_pairs,
                min_liquidity=10000,
                max_spread=0.20,
            )

            if not new_discovered:
                logger.warning("⚠️ Market refresh returned no markets, keeping current list")
                continue

            new_markets = await generate_pairs_dict(min_volume=min_volume, max_pairs=max_pairs)

            # Find markets to remove (in current but not in new)
            old_tokens = set(current_markets.keys())
            new_tokens = set(new_markets.keys())

            tokens_to_remove = old_tokens - new_tokens
            tokens_to_add = new_tokens - old_tokens

            # Cancel orders for removed markets
            if tokens_to_remove:
                logger.info(f"🗑️ Removing {len(tokens_to_remove)} markets that no longer meet criteria")
                for token_id in tokens_to_remove:
                    alias = current_markets.get(token_id, token_id[:12])
                    logger.info(f"   ❌ Removing: {alias}")
                    # Cancel any standing orders
                    await order_manager.cancel_orders_for_market(token_id)
                    # Unsubscribe from market data
                    market_data_engine.unsubscribe_from_market(token_id)
                    # Remove from current markets dict
                    del current_markets[token_id]

            # Add new markets
            if tokens_to_add:
                logger.info(f"➕ Adding {len(tokens_to_add)} new high-volume markets")
                for token_id in tokens_to_add:
                    alias = new_markets.get(token_id, token_id[:12])
                    logger.info(f"   ✅ Adding: {alias}")
                    current_markets[token_id] = alias
                    # Track position for new market (start flat)
                    position_manager.track_position(
                        market_id=token_id,
                        yes_balance=Decimal('0'),
                        no_balance=Decimal('0'),
                        collateral_token_address="0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
                        condition_id=f"condition_{alias.replace(' ', '_')}"
                    )

                # Subscribe to new markets
                await market_data_engine.subscribe_to_markets(list(tokens_to_add))

            logger.info(f"✅ Market refresh complete. Now tracking {len(current_markets)} tokens")

        except Exception as e:
            logger.error(f"💥 Error refreshing markets: {e}")


async def main():
    """Main function to run the market maker bot"""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Polymarket Market Maker Bot')
    parser.add_argument('--mode', choices=['dry-run', 'live', 'backtest'],
                        help='Operation mode: dry-run (mock execution), live (real trading), backtest (historical data)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Run in dry-run mode (mock execution with real data)')
    parser.add_argument('--live', action='store_true',
                        help='Run in live mode (real trading with real funds)')
    parser.add_argument('--backtest', action='store_true',
                        help='Run in backtest mode (historical data replay)')
    parser.add_argument('--data', type=str,
                        help='Path to historical data file for backtesting (e.g., --data ./history/btc_2024.csv)')
    parser.add_argument('--min-volume', type=float, default=100000,
                        help='Minimum volume for market discovery (default: $100,000)')
    parser.add_argument('--max-markets', type=int, default=10,
                        help='Maximum number of markets to trade (default: 10)')
    parser.add_argument('--refresh-interval', type=int, default=3600,
                        help='Market refresh interval in seconds (default: 3600 = 1 hour)')

    args = parser.parse_args()

    # Determine operation mode based on arguments
    if args.mode:
        operation_mode = args.mode
    elif args.dry_run:
        operation_mode = 'dry-run'
    elif args.live:
        operation_mode = 'live'
    elif args.backtest:
        operation_mode = 'backtest'
    else:
        operation_mode = 'dry-run'  # Default mode

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger = logging.getLogger(__name__)

    # Override dry_run setting based on operation mode
    config = load_config()
    if operation_mode == 'dry-run':
        config.dry_run = True
        logger.info("🧪 DRY RUN MODE - Simulated trading with live market data")
    elif operation_mode == 'live':
        config.dry_run = False
        logger.warning("🔴 LIVE MODE - REAL FUNDS WILL BE USED!")
        if not config.api_key or not config.secret_key or not config.wallet_address:
            logger.error("❌ Missing API credentials for live mode")
            sys.exit(1)
    elif operation_mode == 'backtest':
        logger.info(f"📜 BACKTEST MODE - Replaying historical data")
        config.dry_run = True

    # Validate configuration
    if not config.dry_run and (not config.api_key or not config.secret_key or not config.wallet_address):
        raise ValueError("Missing required configuration: API key, secret key, or wallet address")

    # Create credentials object
    credentials = Credentials(
        api_key=config.api_key,
        secret_key=config.secret_key,
        wallet_address=config.wallet_address
    )

    # Initialize REST client with dry run mode if enabled
    rest_client = PolymarketRestClient(credentials, config.base_url, dry_run=config.dry_run)

    logger.info(f"🚀 Initializing bot...")

    # If in dry run mode, initialize additional components
    if config.dry_run:
        logger.info(f"📝 Trade log: {config.dry_run_log_file}")

        # Initialize dry run mode
        dry_run_mode = DryRunMode(
            log_file=config.dry_run_log_file,
            starting_balance=config.starting_balance
        )

        # Initialize simulation engine
        simulation_engine = SimulationEngine(dry_run_mode)

        # Update rest client to use dry run mode
        rest_client.dry_run_mode = dry_run_mode

    # Test REST API connection (skip in dry run mode since no real API calls)
    if not config.dry_run:
        try:
            markets = await rest_client.get_markets()
            logger.info(f"Successfully fetched {len(markets.get('data', []))} markets")
        except Exception as e:
            logger.error(f"Failed to connect to REST API: {e}")
            return

    # Initialize the market data ingestion engine
    market_data_engine = MarketDataIngestionEngine(
        credentials=credentials,
        ws_url=config.ws_url
    )

    # Initialize position manager
    from .api.blockchain_client import PolymarketCTFApiClient
    # Using mock for now - in production this would be a real API client
    from unittest import mock
    mock_api_client = mock.Mock()
    position_manager = PositionManager(mock_api_client)

    # Initialize the RiskManager with safety parameters
    # Max exposure should be higher for multi-market trading
    max_exposure = config_manager.get_max_exposure()
    if max_exposure < 5000:
        max_exposure = Decimal('10000')  # Allow up to $10k exposure for multi-market

    risk_manager = RiskManager(
        position_manager=position_manager,
        max_exposure=max_exposure,
        kill_switch_threshold=config_manager.get_kill_switch_threshold(),  # Loss threshold from config
        fat_finger_threshold=config_manager.get_fat_finger_threshold(),   # Price deviation from config
        starting_balance=config.starting_balance  # Use config value
    )
    logger.info(f"🛡️ Risk Manager: max exposure ${max_exposure}, kill switch {config_manager.get_kill_switch_threshold():.0%}")

    # Initialize the HFMM strategy
    strategy = HFMStrategy(
        position_manager=position_manager,
        target_spread=config_manager.get_target_spread(),  # Target spread from config
        min_order_size=config_manager.get_min_order_size(),
        max_order_size=config_manager.get_max_order_size(),
        num_levels=5
    )

    # Initialize the OrderManager with 1.5s tick interval and 10s cooldown
    order_manager = OrderManager(
        rest_client=rest_client,
        tick_interval_ms=1500,  # Check every 1.5 seconds (not 100ms spam)
        risk_manager=risk_manager
    )

    # Auto-discover high-volume markets from Polymarket API
    min_vol = args.min_volume
    max_mkts = args.max_markets
    logger.info(f"🔍 Discovering markets (min vol: ${min_vol:,.0f}, max: {max_mkts})...")
    discovered_markets = await fetch_markets(
        min_volume=min_vol,
        max_markets=max_mkts,
        min_liquidity=1000,     # Minimum $1k liquidity (Polymarket values are low)
        max_spread=0.25,        # Max 25% spread
    )

    if discovered_markets:
        await print_market_summary(discovered_markets)
        MARKETS = await generate_pairs_dict(min_volume=min_vol, max_pairs=max_mkts)
        logger.info(f"✅ Discovered {len(MARKETS)} token pairs from {len(discovered_markets)} markets")
    else:
        # Fallback to some known high-volume markets
        logger.warning("⚠️ Market discovery failed, using fallback markets")
        MARKETS = {
            "19740329944962592380580142050369523795065853055987745520766432334608119837023": "Bills SB Y",
            "20830052946262425318347897889378986218676355013257249888938222536677638197588": "Bills SB N",
            "28946595841244317705636126646676849578876740730186646421280828201004700559420": "GTA6 $100 Y",
            "42278252558046940014991595990628759801692726198478046188873057685686228021663": "GTA6 $100 N",
        }

    # Reverse lookup for logging
    market_aliases = MARKETS

    def get_alias(token_id: str) -> str:
        """Get human-readable alias for a token ID"""
        return market_aliases.get(token_id, token_id[:20] + "...")

    # Track updates received
    update_counts = {mkt_id: 0 for mkt_id in MARKETS.keys()}

    # Register callbacks for different types of updates
    def on_order_book_update(local_book):
        update_counts[local_book.market_id] = update_counts.get(local_book.market_id, 0) + 1
        alias = get_alias(local_book.market_id)
        best_bid = local_book.get_best_bid()
        best_ask = local_book.get_best_ask()
        if best_bid and best_ask:
            # Only log first update per market and then every 100th
            count = update_counts[local_book.market_id]
            if count == 1 or count % 100 == 0:
                logger.info(f"📈 [{alias}] Bid: {best_bid.price:.3f} | Ask: {best_ask.price:.3f} (update #{count})")

            # If in dry run mode, notify simulation engine of order book update
            if config.dry_run:
                simulation_engine.subscribe_to_market(local_book.market_id, local_book)

    def on_mid_price_update(mid_price, market_id):
        pass  # Reduce noise - mid price shown in main loop

    def on_spread_update(spread, market_id):
        pass  # Reduce noise - spread shown in main loop

    # Register callbacks for all markets
    for market_id in MARKETS.keys():
        market_data_engine.register_update_callback(market_id, on_order_book_update)
        market_data_engine.register_mid_price_callback(market_id, lambda mp, mid=market_id: on_mid_price_update(mp, mid))
        market_data_engine.register_spread_callback(market_id, lambda sp, mid=market_id: on_spread_update(sp, mid))

    try:
        # Start the market data ingestion engine
        await market_data_engine.start()
        logger.info("Market data ingestion engine started")

        # If in dry run mode, start the simulation engine
        if config.dry_run:
            await simulation_engine.start()
            logger.info("Simulation engine started for dry run mode")

        # Start the order manager
        await order_manager.start()
        logger.info("Order manager started")

        # Subscribe to all markets at once (Polymarket requires batch subscription)
        market_ids = list(MARKETS.keys())
        await market_data_engine.subscribe_to_markets(market_ids)

        for market_id, alias in MARKETS.items():
            logger.info(f"📊 Subscribed: {alias}")
            # Add minimal starting positions for demonstration (starts flat)
            position_manager.track_position(
                market_id=market_id,
                yes_balance=Decimal('0'),  # Start with no position
                no_balance=Decimal('0'),
                collateral_token_address="0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
                condition_id=f"condition_{alias.replace(' ', '_')}"
            )
        logger.info(f"✅ Subscribed to {len(MARKETS)} markets")

        # Start the main event loop for order management
        event_loop_task = asyncio.create_task(
            order_manager.run_event_loop(strategy, market_data_engine)
        )

        # Start the market refresh task
        refresh_secs = args.refresh_interval
        market_refresh_task = asyncio.create_task(
            refresh_markets_task(
                market_data_engine=market_data_engine,
                order_manager=order_manager,
                position_manager=position_manager,
                current_markets=MARKETS,
                refresh_interval=refresh_secs,
                min_volume=min_vol,
                max_pairs=max_mkts,
                logger=logger
            )
        )
        logger.info(f"⏰ Market refresh task started (every {refresh_secs//60} min)")

        # Keep the bot running
        last_pnl_snapshot_time = time.time()
        last_config_check_time = time.time()
        last_status_time = time.time()
        message_count = 0

        while True:
            await asyncio.sleep(1)
            current_time = time.time()

            # Check if the risk manager indicates immediate shutdown
            if risk_manager.should_shutdown_immediately():
                logger.critical("Risk manager triggered immediate shutdown!")
                break

            # Check for configuration updates every 30 seconds
            if current_time - last_config_check_time >= 30:
                try:
                    # Check if target spread has been updated
                    new_target_spread = config_manager.get_target_spread()
                    if strategy.target_spread != new_target_spread:
                        strategy.target_spread = new_target_spread
                        logger.info(f"Updated strategy target spread to {new_target_spread}")

                    # Check if max exposure has been updated
                    new_max_exposure = config_manager.get_max_exposure()
                    if risk_manager.max_exposure != new_max_exposure:
                        risk_manager.max_exposure = new_max_exposure
                        logger.info(f"Updated risk manager max exposure to {new_max_exposure}")

                    # Check if other parameters have been updated
                    new_min_order_size = config_manager.get_min_order_size()
                    if strategy.min_order_size != new_min_order_size:
                        strategy.min_order_size = new_min_order_size
                        logger.info(f"Updated strategy min order size to {new_min_order_size}")

                    new_max_order_size = config_manager.get_max_order_size()
                    if strategy.max_order_size != new_max_order_size:
                        strategy.max_order_size = new_max_order_size
                        logger.info(f"Updated strategy max order size to {new_max_order_size}")

                    new_kill_switch_threshold = config_manager.get_kill_switch_threshold()
                    if risk_manager.kill_switch_threshold != new_kill_switch_threshold:
                        risk_manager.kill_switch_threshold = new_kill_switch_threshold
                        logger.info(f"Updated risk manager kill switch threshold to {new_kill_switch_threshold}")

                    new_fat_finger_threshold = config_manager.get_fat_finger_threshold()
                    if risk_manager.fat_finger_threshold != new_fat_finger_threshold:
                        risk_manager.fat_finger_threshold = new_fat_finger_threshold
                        logger.info(f"Updated risk manager fat finger threshold to {new_fat_finger_threshold}")

                    last_config_check_time = current_time
                except Exception as e:
                    logger.error(f"Error checking for configuration updates: {str(e)}")

            # Heartbeat status every 10 seconds
            if current_time - last_status_time >= 10:
                # Get real balances from dry run mode
                if config.dry_run and hasattr(rest_client, 'dry_run_mode'):
                    balances = rest_client.dry_run_mode.get_balances()
                    usdc = balances.get('usdc', config.starting_balance)
                    pnl_stats = rest_client.dry_run_mode.get_total_pnl()
                    total_trades = pnl_stats.get('total_trades', 0)
                    realized_pnl = pnl_stats.get('realized_pnl', 0)
                else:
                    usdc = config.starting_balance
                    total_trades = 0
                    realized_pnl = 0

                # Count markets with data
                markets_with_data = 0
                total_orders = 0
                for mkt_id, alias in MARKETS.items():
                    order_count = await order_manager.get_order_count_for_market(mkt_id)
                    total_orders += order_count
                    if market_data_engine.get_current_mid_price(mkt_id):
                        markets_with_data += 1

                # Show status with PnL
                ws_status = "🟢" if market_data_engine.connection_manager.ws_client and market_data_engine.connection_manager.ws_client.is_connected else "🔴"
                pnl_emoji = "📈" if realized_pnl >= 0 else "📉"
                logger.info(f"💓 {ws_status} WS | 📊 {markets_with_data}/{len(MARKETS)} mkts | 💼 {total_orders} orders | 🔄 {total_trades} fills | {pnl_emoji} ${realized_pnl:+.2f} PnL | 💰 ${usdc:.2f}")

                # Show per-market stats every 30 seconds
                if int(current_time) % 30 < 10 and config.dry_run and hasattr(rest_client, 'dry_run_mode'):
                    for mkt_id, alias in MARKETS.items():
                        mid_price = market_data_engine.get_current_mid_price(mkt_id)
                        spread = market_data_engine.get_current_spread(mkt_id)
                        if mid_price:
                            stats = rest_client.dry_run_mode.get_market_stats(mkt_id)
                            trades = stats.get('trades', 0)
                            mkt_pnl = stats.get('pnl', 0)
                            spread_bps = float(spread * 10000) if spread else 0
                            logger.info(f"   📌 {alias}: Mid {mid_price:.4f} | Spread {spread_bps:.0f}bps | Trades {trades} | PnL ${mkt_pnl:+.2f}")

                last_status_time = current_time

    except KeyboardInterrupt:
        logger.info("👋 Shutting down...")
    except Exception as e:
        logger.error(f"💥 Error in main loop: {e}")
    finally:
        # Cancel background tasks
        if 'event_loop_task' in locals():
            event_loop_task.cancel()
            try:
                await event_loop_task
            except asyncio.CancelledError:
                pass

        if 'market_refresh_task' in locals():
            market_refresh_task.cancel()
            try:
                await market_refresh_task
            except asyncio.CancelledError:
                pass

        # Stop the order manager
        await order_manager.stop()

        # Stop the market data engine
        await market_data_engine.stop()

        # If in dry run mode, generate reports
        if config.dry_run:
            logger.info("Generating dry run reports...")
            try:
                # Generate PnL chart
                rest_client.dry_run_mode.generate_pnl_graph("pnl_chart.png")

                # Generate detailed report
                report = rest_client.dry_run_mode.generate_detailed_report("pnl_detailed_report.txt")
                logger.info("Dry run reports generated successfully")
                print(report)
            except Exception as e:
                logger.error(f"Error generating dry run reports: {e}")


if __name__ == "__main__":
    asyncio.run(main())