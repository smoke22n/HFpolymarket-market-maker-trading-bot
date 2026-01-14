"""
Simulation Engine for Dry Run Mode

This module implements the simulation engine that monitors order books and 
determines when simulated orders should be filled based on market price movements.
"""
import asyncio
import logging
import time
from typing import Dict, List, Optional, Callable
from decimal import Decimal
from dataclasses import dataclass
from datetime import datetime

from ..market_data.order_book_engine import LocalOrderBook
from ..utils.dry_run import DryRunMode


@dataclass
class FillEvent:
    """Represents a simulated fill event"""
    order_id: str
    market_id: str
    side: str
    price: Decimal
    quantity_filled: Decimal
    timestamp: float


class SimulationEngine:
    """
    Simulation engine that monitors order books and simulates fills based on market data.
    Works in conjunction with DryRunMode to update inventory when orders are filled.
    """
    
    def __init__(self, dry_run_mode: DryRunMode):
        self.dry_run_mode = dry_run_mode
        self.logger = logging.getLogger(__name__)
        self.is_running = False
        self.fill_callbacks: List[Callable[[FillEvent], None]] = []
        self.market_subscriptions: Dict[str, LocalOrderBook] = {}
        
    def subscribe_to_market(self, market_id: str, local_order_book: LocalOrderBook):
        """Subscribe to a market for fill simulation"""
        self.market_subscriptions[market_id] = local_order_book
        self.logger.info(f"Subscribed to market {market_id} for fill simulation")
        
    def unsubscribe_from_market(self, market_id: str):
        """Unsubscribe from a market"""
        if market_id in self.market_subscriptions:
            del self.market_subscriptions[market_id]
            self.logger.info(f"Unsubscribed from market {market_id}")
    
    def register_fill_callback(self, callback: Callable[[FillEvent], None]):
        """Register a callback to be called when an order is filled"""
        self.fill_callbacks.append(callback)
    
    async def start(self):
        """Start the simulation engine"""
        self.is_running = True
        self.logger.info("Simulation engine started")
        
        # Start the main simulation loop
        asyncio.create_task(self._simulation_loop())
    
    async def stop(self):
        """Stop the simulation engine"""
        self.is_running = False
        self.logger.info("Simulation engine stopped")
    
    async def _simulation_loop(self):
        """Main loop that checks for fills based on order book movements"""
        while self.is_running:
            try:
                # Check each subscribed market for potential fills
                for market_id, local_book in self.market_subscriptions.items():
                    # Get current order book state
                    order_book_snapshot = local_book.get_order_book_state()
                    
                    # Convert to the format expected by dry_run_mode.simulate_fills
                    current_order_book = {
                        'bids': [{'price': str(entry.price), 'size': str(entry.size)} 
                                for entry in order_book_snapshot.bids],
                        'asks': [{'price': str(entry.price), 'size': str(entry.size)} 
                                for entry in order_book_snapshot.asks]
                    }
                    
                    # Simulate fills for this market
                    filled_orders = self.dry_run_mode.simulate_fills(market_id, current_order_book)
                    
                    # Trigger callbacks for each filled order
                    for dry_order in filled_orders:
                        fill_event = FillEvent(
                            order_id=dry_order.order_id,
                            market_id=dry_order.market_id,
                            side=dry_order.side,
                            price=dry_order.filled_price or Decimal('0'),
                            quantity_filled=dry_order.filled_quantity or Decimal('0'),
                            timestamp=time.time()
                        )
                        
                        for callback in self.fill_callbacks:
                            try:
                                callback(fill_event)
                            except Exception as e:
                                self.logger.error(f"Error in fill callback: {e}")
                
                # Record PnL for each market
                for market_id in self.market_subscriptions.keys():
                    self.dry_run_mode.record_pnl(market_id)
                
                # Small delay to prevent excessive CPU usage
                await asyncio.sleep(0.1)  # Check every 100ms
                
            except Exception as e:
                self.logger.error(f"Error in simulation loop: {e}")
                await asyncio.sleep(1)  # Wait before retrying
    
    def get_simulation_stats(self) -> Dict[str, any]:
        """Get statistics about the simulation"""
        return {
            "active_orders": len(self.dry_run_mode.orders),
            "filled_orders": len(self.dry_run_mode.filled_orders),
            "total_pnl": float(sum([record.pnl for record in self.dry_run_mode.pnl_records])),
            "markets_tracked": len(self.market_subscriptions),
            "log_entries": len(self.dry_run_mode.logs)
        }


# Helper function to integrate with the existing system
def create_dry_run_components(starting_balance: Decimal = Decimal('10000')):
    """
    Helper function to create dry run components for integration.
    
    Args:
        starting_balance: Initial balance for the simulation
        
    Returns:
        Tuple of (dry_run_mode, simulation_engine, rest_client_wrapper)
    """
    from ..utils.dry_run import DryRunMode
    import time
    
    # Create dry run mode instance
    dry_run_mode = DryRunMode(starting_balance=starting_balance)
    
    # Create a wrapper for the rest client that enables dry run
    class DryRunRestClientWrapper:
        def __init__(self, dry_run_mode):
            self.dry_run_mode = dry_run_mode
            
        async def place_order(self, order_params):
            return self.dry_run_mode.place_order(order_params)
            
        async def cancel_order(self, order_id):
            return self.dry_run_mode.cancel_order(order_id)
            
        async def get_orders(self, **filters):
            return self.dry_run_mode.get_orders(**filters)
            
        async def get_balances(self):
            return self.dry_run_mode.get_balances()
    
    rest_client_wrapper = DryRunRestClientWrapper(dry_run_mode)
    
    # Create simulation engine
    simulation_engine = SimulationEngine(dry_run_mode)
    
    return dry_run_mode, simulation_engine, rest_client_wrapper