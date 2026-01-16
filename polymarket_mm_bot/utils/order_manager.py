"""
Order Manager for tracking and managing active orders in the market making bot.
Implements the order lifecycle and cancel-replace functionality.
"""
import asyncio
import logging
import time
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime

from ..api.client import PolymarketRestClient
from ..strategies.hfmm_strategy import Order, OrderBatcher
from ..market_data.order_book_engine import LocalOrderBook
from .database import db_manager


@dataclass
class ActiveOrder:
    """Represents an order that is currently active on the exchange"""
    order_id: str
    market_id: str
    side: str  # 'buy' or 'sell'
    price: Decimal
    size: Decimal
    placed_at: datetime
    original_order: Order  # Reference to the original strategy-generated order


class OrderManager:
    """
    Manages the lifecycle of orders including placement, tracking, cancellation, and replacement.
    """

    def __init__(self, rest_client: PolymarketRestClient, tick_interval_ms: int = 1500, risk_manager=None):
        """
        Initialize the OrderManager.

        Args:
            rest_client: Instance of PolymarketRestClient for API interactions
            tick_interval_ms: Interval in milliseconds between ticks (default 1500ms = 1.5s)
            risk_manager: Optional RiskManager instance for risk checks
        """
        self.rest_client = rest_client
        self.tick_interval_ms = tick_interval_ms
        self.risk_manager = risk_manager
        self.active_orders: Dict[str, ActiveOrder] = {}  # order_id -> ActiveOrder
        self.market_orders: Dict[str, Set[str]] = {}  # market_id -> set of order_ids
        self.last_replacement_time: Dict[str, float] = {}  # market_id -> timestamp
        self.replacement_cooldown = 10.0  # Minimum 10 seconds between replacements per market
        self.logger = logging.getLogger(__name__)
        self.is_running = False
        self._lock = asyncio.Lock()  # Async lock for thread safety

    async def start(self):
        """Start the order manager"""
        self.is_running = True
        self.logger.info(f"🎯 OrderManager started (tick: {self.tick_interval_ms}ms, cooldown: {self.replacement_cooldown}s)")

    async def stop(self):
        """Stop the order manager and cancel all active orders"""
        self.is_running = False
        self.logger.info("🛑 Stopping OrderManager, cancelling all orders...")
        await self.cancel_all_orders()
        self.logger.info("✅ OrderManager stopped cleanly")

    async def place_orders(self, orders: List[Order]) -> List[ActiveOrder]:
        """
        Place a batch of orders on the exchange and track them.

        Args:
            orders: List of Order objects to place

        Returns:
            List of ActiveOrder objects representing the placed orders
        """
        if not orders:
            return []

        placed_orders = []

        # Place orders individually to track them properly
        for order in orders:
            # Perform risk checks if risk manager is available
            if self.risk_manager:
                # Get reference price for fat finger check
                # For now, we'll use the order's current price as a fallback
                reference_price = order.price

                # Perform risk checks
                is_safe, violations = self.risk_manager.check_order_risks(
                    market_id=order.market_id,
                    order_price=order.price,
                    reference_price=reference_price
                )

                if not is_safe:
                    self.logger.warning(
                        f"Risk check failed for order in market {order.market_id}, "
                        f"violations: {', '.join(violations)}. Order rejected."
                    )
                    continue  # Skip placing this order

            try:
                # Prepare order parameters for API
                order_params = {
                    'marketId': order.market_id,
                    'side': order.side,
                    'price': str(order.price),
                    'quantity': str(order.size),
                    'type': order.order_type,
                    'timeInForce': 'GTC'  # Good till cancelled
                }

                # Place the order
                response = await self.rest_client.place_order(order_params)

                # Check if the order was placed successfully
                if 'order_id' in response or 'orderId' in response:
                    order_id = response.get('order_id', response.get('orderId'))

                    active_order = ActiveOrder(
                        order_id=order_id,
                        market_id=order.market_id,
                        side=order.side,
                        price=order.price,
                        size=order.size,
                        placed_at=datetime.now(),
                        original_order=order
                    )

                    # Track the order
                    async with self._lock:
                        self.active_orders[order_id] = active_order
                        if order.market_id not in self.market_orders:
                            self.market_orders[order.market_id] = set()
                        self.market_orders[order.market_id].add(order_id)

                    # Save to database
                    try:
                        db_manager.save_active_order(
                            order_id=order_id,
                            market_id=order.market_id,
                            side=order.side,
                            price=order.price,
                            size=order.size,
                            status='open'
                        )
                    except Exception as e:
                        self.logger.error(f"Error saving order to database: {str(e)}")

                    placed_orders.append(active_order)
                    self.logger.debug(f"Placed order {order_id}: {order.side.upper()} {order.size} @ {order.price}")
                else:
                    self.logger.error(f"Failed to place order for {order.market_id}: {response}")

            except Exception as e:
                self.logger.error(f"Error placing order for {order.market_id}: {str(e)}")

        return placed_orders

    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a specific order by ID.

        Args:
            order_id: ID of the order to cancel

        Returns:
            True if successful, False otherwise
        """
        try:
            response = await self.rest_client.cancel_order(order_id)
            
            # Check if cancellation was successful
            success = 'success' in response or 'status' in response
            
            if success:
                # Remove from tracking
                async with self._lock:
                    if order_id in self.active_orders:
                        active_order = self.active_orders[order_id]
                        # Remove from market-specific tracking
                        if active_order.market_id in self.market_orders:
                            self.market_orders[active_order.market_id].discard(order_id)
                        # Remove from global tracking
                        del self.active_orders[order_id]

                # Update database
                try:
                    db_manager.update_order_status(order_id, 'cancelled')
                except Exception as e:
                    self.logger.error(f"Error updating order status in database: {str(e)}")

                self.logger.debug(f"Cancelled order {order_id}")
                return True
            else:
                self.logger.error(f"Failed to cancel order {order_id}: {response}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error cancelling order {order_id}: {str(e)}")
            return False

    async def cancel_orders_for_market(self, market_id: str) -> bool:
        """
        Cancel all orders for a specific market.

        Args:
            market_id: ID of the market

        Returns:
            True if successful, False otherwise
        """
        order_ids_to_cancel = []
        
        async with self._lock:
            if market_id in self.market_orders:
                order_ids_to_cancel = list(self.market_orders[market_id])
        
        success_count = 0
        for order_id in order_ids_to_cancel:
            if await self.cancel_order(order_id):
                success_count += 1

        if order_ids_to_cancel:
            self.logger.debug(f"Cancelled {success_count}/{len(order_ids_to_cancel)} orders for market")
        return success_count == len(order_ids_to_cancel)

    async def cancel_all_orders(self) -> bool:
        """
        Cancel all active orders.

        Returns:
            True if all cancellations were successful, False otherwise
        """
        all_order_ids = []
        
        async with self._lock:
            all_order_ids = list(self.active_orders.keys())
        
        success_count = 0
        for order_id in all_order_ids:
            if await self.cancel_order(order_id):
                success_count += 1

        if all_order_ids:
            self.logger.info(f"🛑 Cancelled {success_count}/{len(all_order_ids)} total orders")
        return success_count == len(all_order_ids)

    async def get_active_orders_for_market(self, market_id: str) -> List[ActiveOrder]:
        """
        Get all active orders for a specific market.

        Args:
            market_id: ID of the market

        Returns:
            List of ActiveOrder objects
        """
        result = []
        async with self._lock:
            if market_id in self.market_orders:
                for order_id in self.market_orders[market_id]:
                    if order_id in self.active_orders:
                        result.append(self.active_orders[order_id])
        return result

    async def are_orders_stale(self, market_id: str, max_age_seconds: float = 30.0) -> bool:
        """
        Check if orders for a market are stale (older than max_age_seconds).

        Args:
            market_id: ID of the market
            max_age_seconds: Maximum age in seconds before orders are considered stale

        Returns:
            True if orders are stale, False otherwise
        """
        active_orders = await self.get_active_orders_for_market(market_id)
        if not active_orders:
            return False  # No orders, so not stale

        current_time = datetime.now()
        for active_order in active_orders:
            age = (current_time - active_order.placed_at).total_seconds()
            if age > max_age_seconds:
                return True

        return False

    async def should_replace_orders(self, market_id: str, current_orders: List[Order],
                             threshold: Decimal = Decimal('0.005')) -> bool:
        """
        Determine if existing orders should be replaced based on price differences.
        Uses a higher threshold (50 bps default) to avoid excessive requoting.

        Args:
            market_id: ID of the market
            current_orders: New orders generated by the strategy
            threshold: Price difference threshold to trigger replacement (default 50 bps)

        Returns:
            True if orders should be replaced, False otherwise
        """
        existing_orders = await self.get_active_orders_for_market(market_id)

        # If no existing orders, we should place new ones
        if not existing_orders:
            self.logger.info(f"🆕 No existing orders for market, placing fresh quotes")
            return True

        # If no new orders from strategy, we should cancel existing ones
        if not current_orders:
            return True

        # Compare prices of existing vs new orders - only replace if significant move
        existing_buy_prices = {o.price for o in existing_orders if o.side == 'buy'}
        existing_sell_prices = {o.price for o in existing_orders if o.side == 'sell'}

        new_buy_prices = {o.price for o in current_orders if o.side == 'buy'}
        new_sell_prices = {o.price for o in current_orders if o.side == 'sell'}

        # Check best bid/ask specifically (level 0) - most important prices
        if new_buy_prices and existing_buy_prices:
            best_new_bid = max(new_buy_prices)
            best_existing_bid = max(existing_buy_prices)
            if abs(best_new_bid - best_existing_bid) > threshold:
                self.logger.info(f"📊 Bid moved {abs(best_new_bid - best_existing_bid):.4f} > threshold {threshold}")
                return True

        if new_sell_prices and existing_sell_prices:
            best_new_ask = min(new_sell_prices)
            best_existing_ask = min(existing_sell_prices)
            if abs(best_new_ask - best_existing_ask) > threshold:
                self.logger.info(f"📊 Ask moved {abs(best_new_ask - best_existing_ask):.4f} > threshold {threshold}")
                return True

        return False

    async def replace_orders_for_market(self, market_id: str, new_orders: List[Order]) -> bool:
        """
        Replace all orders for a market with new ones (cancel and replace pattern).

        Args:
            market_id: ID of the market
            new_orders: New orders to place

        Returns:
            True if successful, False otherwise
        """
        active_orders_list = await self.get_active_orders_for_market(market_id)
        num_existing = len(active_orders_list)

        # Get best bid/ask from new orders for logging
        buy_orders = [o for o in new_orders if o.side == 'buy']
        sell_orders = [o for o in new_orders if o.side == 'sell']
        best_bid = max((o.price for o in buy_orders), default=None)
        best_ask = min((o.price for o in sell_orders), default=None)

        # Short market ID for logging
        short_id = market_id[:8] + "..."

        if num_existing > 0:
            # Cancel existing orders quietly (reduce log spam)
            await self.cancel_orders_for_market(market_id)

        # Place new orders
        if new_orders:
            placed_orders = await self.place_orders(new_orders)
            if len(placed_orders) == len(new_orders):
                spread = (best_ask - best_bid) if (best_bid and best_ask) else None
                spread_bps = float(spread * 10000) if spread else 0
                self.logger.info(f"💰 [{short_id}] Quoted {len(buy_orders)}x{len(sell_orders)} | "
                               f"Bid: {best_bid:.4f} | Ask: {best_ask:.4f} | Spread: {spread_bps:.0f}bps")
                return True
            else:
                self.logger.warning(f"⚠️ [{short_id}] Only placed {len(placed_orders)}/{len(new_orders)} orders")
                return False
        else:
            self.logger.info(f"🔇 [{short_id}] No orders to place")
            return True

    def _can_replace_orders(self, market_id: str) -> bool:
        """Check if enough time has passed since last replacement for this market."""
        last_time = self.last_replacement_time.get(market_id, 0)
        time_since_last = time.time() - last_time
        return time_since_last >= self.replacement_cooldown

    async def run_event_loop(self, strategy, market_data_engine):
        """
        Main event loop that compares active orders with ideal orders and manages replacements.
        Uses cooldowns to prevent excessive requoting and let orders rest to get filled.

        Args:
            strategy: The strategy instance that generates orders
            market_data_engine: The market data engine providing order book updates
        """
        self.logger.info("🚀 Starting order management event loop (tick: %dms, cooldown: %.0fs)",
                        self.tick_interval_ms, self.replacement_cooldown)

        while self.is_running:
            start_time = time.time()

            try:
                # Iterate through all markets in the market data engine
                for market_id in list(market_data_engine.local_order_books.keys()):
                    # Get the current local order book for this market
                    local_book = market_data_engine.get_local_order_book(market_id)
                    if not local_book:
                        continue

                    # Skip if no mid price (no data yet)
                    mid_price = local_book.get_mid_price()
                    if not mid_price:
                        continue

                    # Generate new ideal orders from the strategy
                    ideal_orders = strategy.generate_orders(market_id, local_book)

                    # Check cooldown first - don't spam replacements
                    if not self._can_replace_orders(market_id):
                        continue  # Still in cooldown, let orders rest

                    # Check if we need to replace orders
                    needs_replacement = False
                    reason = ""

                    # Check for stale orders (30+ seconds old)
                    if await self.are_orders_stale(market_id, max_age_seconds=30.0):
                        needs_replacement = True
                        reason = "⏰ Orders stale (30s+)"
                    # Check for significant price movement
                    elif await self.should_replace_orders(market_id, ideal_orders):
                        needs_replacement = True
                        reason = "📈 Price moved significantly"

                    if needs_replacement:
                        self.logger.info(f"{reason} - requoting")
                        await self.replace_orders_for_market(market_id, ideal_orders)
                        self.last_replacement_time[market_id] = time.time()

            except Exception as e:
                self.logger.error(f"💥 Error in event loop: {str(e)}")

            # Wait for the next tick, accounting for processing time
            elapsed = time.time() - start_time
            sleep_time = max((self.tick_interval_ms / 1000.0) - elapsed, 0)
            await asyncio.sleep(sleep_time)

    async def get_order_count_for_market(self, market_id: str) -> int:
        """
        Get the count of active orders for a specific market.

        Args:
            market_id: ID of the market

        Returns:
            Number of active orders for the market
        """
        active_orders = await self.get_active_orders_for_market(market_id)
        return len(active_orders)