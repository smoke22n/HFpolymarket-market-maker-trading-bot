"""
Background task runner for the Polymarket MM Bot
Manages the HFT loop independently of the API server
"""
import asyncio
import logging
import threading
import time
from typing import Optional, Dict, Any
from enum import Enum
from decimal import Decimal
from dataclasses import dataclass

from ..main import main as run_trading_bot
from ..utils.database import db_manager
from ..utils.config_manager import config_manager
from ..utils.risk_manager import RiskManager, RiskMetrics
from ..utils.position_manager import PositionManager


class BotState(Enum):
    """Enumeration of possible bot states"""
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    PANIC_SELLING = "panic_selling"


@dataclass
class TradingStats:
    """Data class to hold current trading statistics"""
    pnl: Decimal = Decimal('0')
    open_exposure: Decimal = Decimal('0')
    win_loss_ratio: Decimal = Decimal('0')
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    current_state: BotState = BotState.STOPPED


class BackgroundRunner:
    """
    Manages the background execution of the trading bot
    Allows the HFT loop to run independently of the API server
    """
    
    def __init__(self):
        self.bot_task: Optional[asyncio.Task] = None
        self.bot_thread: Optional[threading.Thread] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.state = BotState.STOPPED
        self.stats = TradingStats()
        self.logger = logging.getLogger(__name__)
        
        # Event to signal when to pause/resume the bot
        self.pause_event = asyncio.Event()
        self.pause_event.set()  # Initially not paused
        
        # Event to signal panic sell
        self.panic_sell_event = asyncio.Event()
        
        # Reference to shared components
        self.position_manager: Optional[PositionManager] = None
        self.risk_manager: Optional[RiskManager] = None
        
    def start_bot(self) -> bool:
        """Start the trading bot in a background thread"""
        if self.state in [BotState.RUNNING, BotState.PANIC_SELLING]:
            self.logger.warning("Bot is already running")
            return False
            
        # Create a new event loop for the background thread
        self.loop = asyncio.new_event_loop()
        self.bot_thread = threading.Thread(
            target=self._run_bot_in_thread,
            args=(self.loop,),
            daemon=True
        )
        self.bot_thread.start()
        
        # Wait briefly to see if the bot starts successfully
        time.sleep(1)
        if self.state == BotState.RUNNING:
            return True
        else:
            return False

    def _run_bot_in_thread(self, loop: asyncio.AbstractEventLoop):
        """Run the bot in a separate thread with its own event loop"""
        asyncio.set_event_loop(loop)
        
        async def run_bot():
            self.state = BotState.RUNNING
            try:
                # This would be the actual bot main function
                # For now, we'll simulate the bot running
                await self._simulate_bot_loop()
            except Exception as e:
                self.logger.error(f"Error in bot loop: {e}")
                self.state = BotState.STOPPED
            finally:
                self.state = BotState.STOPPED
                
        loop.run_until_complete(run_bot())

    async def _simulate_bot_loop(self):
        """Simulate the bot loop - this would be replaced with the actual main function"""
        # In a real implementation, this would be the actual trading loop from main.py
        # For now, we'll simulate the bot behavior
        while self.state != BotState.STOPPED:
            # Wait for pause event to be cleared (when paused)
            await self.pause_event.wait()
            
            # Check for panic sell
            if self.panic_sell_event.is_set():
                await self._perform_panic_sell()
                self.panic_sell_event.clear()
                
            # Update stats periodically
            await self._update_stats()
            
            # Sleep for a short interval to prevent busy-waiting
            await asyncio.sleep(1)

    async def _update_stats(self):
        """Update trading statistics"""
        # Get latest PnL from database
        try:
            # Get the latest PnL snapshot
            db_session = db_manager.SessionLocal()
            try:
                latest_snapshot = db_session.query(db_manager.__class__.__dict__['PnLSnapshot']).order_by(
                    db_manager.__class__.__dict__['PnLSnapshot'].timestamp.desc()
                ).first()

                if latest_snapshot:
                    self.stats.pnl = Decimal(str(latest_snapshot.cumulative_pnl))
            finally:
                db_session.close()

            # Calculate open exposure from position manager if available
            if self.position_manager:
                total_exposure = Decimal('0')
                for market_id, position in self.position_manager.positions.items():
                    # Calculate unhedged exposure for this market
                    hedged_sets = min(position.yes_balance, position.no_balance)
                    unhedged_exposure = (position.yes_balance + position.no_balance) - hedged_sets
                    total_exposure += unhedged_exposure
                self.stats.open_exposure = total_exposure

            # Calculate win/loss ratio from trade history
            db_session = db_manager.SessionLocal()
            try:
                trades = db_session.query(db_manager.__class__.__dict__['Trade']).all()
                self.stats.total_trades = len(trades)

                # For simplicity, we'll calculate win/loss ratio based on realized PnL from trades
                # In a real implementation, you'd need a more sophisticated PnL tracking system
                winning_trades = 0
                losing_trades = 0

                # Since we don't have individual trade PnL in the schema, we'll use a simplified approach
                # where we look at the overall trend in PnL snapshots
                pnl_snapshots = db_session.query(db_manager.__class__.__dict__['PnLSnapshot']).all()

                if len(pnl_snapshots) > 1:
                    # Compare consecutive PnL snapshots to determine winning/losing periods
                    prev_pnl = Decimal(str(pnl_snapshots[0].cumulative_pnl))

                    for snapshot in pnl_snapshots[1:]:
                        current_pnl = Decimal(str(snapshot.cumulative_pnl))
                        if current_pnl > prev_pnl:
                            winning_trades += 1
                        elif current_pnl < prev_pnl:
                            losing_trades += 1
                        prev_pnl = current_pnl

                self.stats.winning_trades = winning_trades
                self.stats.losing_trades = losing_trades

                if self.stats.losing_trades > 0:
                    self.stats.win_loss_ratio = Decimal(str(self.stats.winning_trades / self.stats.losing_trades))
                elif self.stats.winning_trades > 0:
                    self.stats.win_loss_ratio = Decimal('inf')  # Infinite if no losing trades
                else:
                    self.stats.win_loss_ratio = Decimal('0')
            finally:
                db_session.close()

        except Exception as e:
            self.logger.error(f"Error updating stats: {e}")

    def stop_bot(self) -> bool:
        """Stop the trading bot"""
        if self.state == BotState.STOPPED:
            return True  # Already stopped
            
        if self.state == BotState.RUNNING:
            self.state = BotState.STOPPED
            if self.bot_task:
                self.bot_task.cancel()
            return True
        else:
            # For now, just set the state to stopped
            self.state = BotState.STOPPED
            return True

    def pause_bot(self) -> bool:
        """Pause the trading bot"""
        if self.state == BotState.RUNNING:
            self.state = BotState.PAUSED
            self.pause_event.clear()  # Clear the event to pause the loop
            return True
        return False

    def resume_bot(self) -> bool:
        """Resume the trading bot"""
        if self.state == BotState.PAUSED:
            self.state = BotState.RUNNING
            self.pause_event.set()  # Set the event to resume the loop
            return True
        return False

    async def _perform_panic_sell(self):
        """Perform panic sell - liquidate all positions"""
        self.state = BotState.PANIC_SELLING
        try:
            # In a real implementation, this would liquidate all positions
            # For now, we'll just log the action
            self.logger.info("PANIC SELL: Liquidating all positions...")
            
            # Update stats to reflect panic sell state
            self.stats.current_state = BotState.PANIC_SELLING
            
            # After panic sell, return to paused state
            self.state = BotState.PAUSED
            self.pause_event.clear()
            
        except Exception as e:
            self.logger.error(f"Error during panic sell: {e}")
            self.state = BotState.PAUSED

    def trigger_panic_sell(self) -> bool:
        """Trigger panic sell to liquidate all positions"""
        if self.state in [BotState.RUNNING, BotState.PAUSED]:
            self.panic_sell_event.set()
            return True
        return False

    def get_stats(self) -> TradingStats:
        """Get current trading statistics"""
        return self.stats

    def get_state(self) -> BotState:
        """Get current bot state"""
        return self.state

    def update_config(self, param_name: str, param_value: str) -> bool:
        """Update bot configuration parameter"""
        try:
            # Use the config manager to update the parameter
            if param_name == "target_spread":
                config_manager.set_target_spread(Decimal(param_value))
            elif param_name == "max_exposure":
                config_manager.set_max_exposure(Decimal(param_value))
            elif param_name == "min_order_size":
                config_manager.set_min_order_size(Decimal(param_value))
            elif param_name == "max_order_size":
                config_manager.set_max_order_size(Decimal(param_value))
            elif param_name == "kill_switch_threshold":
                config_manager.set_kill_switch_threshold(Decimal(param_value))
            elif param_name == "fat_finger_threshold":
                config_manager.set_fat_finger_threshold(Decimal(param_value))
            else:
                self.logger.warning(f"Unknown parameter: {param_name}")
                return False

            return True
        except Exception as e:
            self.logger.error(f"Error updating config: {e}")
            return False

    def get_all_configs(self):
        """Get all bot configuration parameters"""
        try:
            # Use the database manager to get all configurations
            configs = db_manager.get_all_bot_configs()
            return configs
        except Exception as e:
            self.logger.error(f"Error getting configs: {e}")
            return []