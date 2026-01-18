"""
Dry Run Mode Implementation for Polymarket Market Maker Bot

This module implements a dry run mode that simulates trading without making real API calls.
Instead of sending real orders, it logs actions to a JSON file and simulates fills based on
the real order book data.
"""
import asyncio
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, asdict
from decimal import Decimal
from pathlib import Path
from .database import db_manager

# Import visualization libraries only when needed
def _import_visualization_libs():
    """Import visualization libraries only when needed to avoid dependency issues"""
    try:
        import matplotlib.pyplot as plt
        import pandas as pd
        return plt, pd
    except ImportError:
        raise ImportError("matplotlib and pandas are required for generating charts. Install with: pip install matplotlib pandas")


@dataclass
class DryRunOrder:
    """Represents an order in dry run mode"""
    order_id: str
    market_id: str
    side: str  # 'buy' or 'sell'
    price: Decimal
    quantity: Decimal
    placed_at: float
    filled: bool = False
    filled_at: Optional[float] = None
    filled_price: Optional[Decimal] = None
    filled_quantity: Optional[Decimal] = None


@dataclass
class PnLRecord:
    """Record of profit and loss at a specific time"""
    timestamp: float
    datetime: datetime
    market_id: str
    pnl: Decimal
    yes_balance: Decimal
    no_balance: Decimal
    usdc_balance: Decimal


class DryRunMode:
    """
    Implements dry run mode for the Polymarket bot.
    
    Features:
    1. Logs 'Order Placed' and 'Order Cancelled' actions to a JSON file
    2. Simulates fills based on real order book data
    3. Updates fake inventory when orders are filled
    4. Outputs PnL graph at the end of the session
    """
    
    def __init__(self, log_file: str = "dry_run_log.json", starting_balance: Decimal = Decimal('10000')):
        self.log_file = log_file
        self.starting_balance = starting_balance
        self.orders: Dict[str, DryRunOrder] = {}
        self.logs: List[Dict[str, Any]] = []
        self.pnl_records: List[PnLRecord] = []
        
        # Initialize balances
        self.usdc_balance = self.starting_balance
        self.yes_balances: Dict[str, Decimal] = {}
        self.no_balances: Dict[str, Decimal] = {}
        
        # Track filled orders for PnL calculation
        self.filled_orders: List[DryRunOrder] = []

        # Per-market PnL tracking
        self.market_pnl: Dict[str, Decimal] = {}  # market_id -> realized PnL
        self.market_trades: Dict[str, int] = {}  # market_id -> trade count
        self.total_fees_paid: Decimal = Decimal('0')

        # Initialize balances for each market
        self.initial_balances: Dict[str, Dict[str, Decimal]] = {}
        
    def log_action(self, action: str, details: Dict[str, Any]):
        """Log an action to the dry run log"""
        log_entry = {
            "timestamp": time.time(),
            "datetime": datetime.fromtimestamp(time.time()).isoformat(),
            "action": action,
            "details": details
        }
        self.logs.append(log_entry)
        
        # Write to file immediately to persist logs
        with open(self.log_file, 'w') as f:
            json.dump(self.logs, f, indent=2, default=str)
    
    def place_order(self, order_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simulate placing an order - log the action and store the order locally.
        
        Args:
            order_params: Dictionary containing order parameters
            
        Returns:
            Dictionary with order_id and status
        """
        order_id = f"dry_run_{int(time.time() * 1000000)}"
        
        # Create a dry run order object
        dry_order = DryRunOrder(
            order_id=order_id,
            market_id=order_params['marketId'],
            side=order_params['side'],
            price=Decimal(str(order_params['price'])),
            quantity=Decimal(str(order_params['quantity'])),
            placed_at=time.time()
        )
        
        # Store the order
        self.orders[order_id] = dry_order
        
        # Log the action
        self.log_action("ORDER_PLACED", {
            "order_id": order_id,
            "market_id": order_params['marketId'],
            "side": order_params['side'],
            "price": str(dry_order.price),
            "quantity": str(dry_order.quantity)
        })
        
        return {
            "order_id": order_id,
            "status": "placed",
            "timestamp": time.time()
        }
    
    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        Simulate cancelling an order - log the action and remove from tracking.
        
        Args:
            order_id: ID of the order to cancel
            
        Returns:
            Dictionary with status
        """
        if order_id in self.orders:
            order = self.orders[order_id]
            
            # Remove the order
            del self.orders[order_id]
            
            # Log the action
            self.log_action("ORDER_CANCELLED", {
                "order_id": order_id,
                "market_id": order.market_id,
                "side": order.side,
                "price": str(order.price),
                "quantity": str(order.quantity)
            })
            
            return {
                "order_id": order_id,
                "status": "cancelled",
                "timestamp": time.time()
            }
        else:
            return {
                "status": "error",
                "message": f"Order {order_id} not found"
            }
    
    def simulate_fills(self, market_id: str, current_order_book: Dict[str, Any]) -> List[DryRunOrder]:
        """
        Simulate fills based on the current order book data.
        If the market price crosses my fake order price, assume it was filled.
        
        Args:
            market_id: ID of the market to check for fills
            current_order_book: Current order book data with bids and asks
            
        Returns:
            List of filled orders
        """
        filled_orders = []
        
        # Get current bids and asks from the order book
        bids = current_order_book.get('bids', [])
        asks = current_order_book.get('asks', [])
        
        # Check buy orders against current asks (if there's a matching ask at or below my bid price)
        for order_id, order in list(self.orders.items()):  # Use list() to avoid dict change during iteration
            if order.market_id != market_id:
                continue
                
            if order.side == 'buy' and not order.filled:
                # Check if any ask is at or below my bid price
                for ask in asks:
                    ask_price = Decimal(str(ask['price']))
                    ask_size = Decimal(str(ask['size']))
                    
                    if ask_price <= order.price:
                        # Fill the order
                        fill_qty = min(order.quantity, ask_size)
                        
                        # Update order status
                        order.filled = True
                        order.filled_at = time.time()
                        order.filled_price = ask_price
                        order.filled_quantity = fill_qty
                        
                        # Update balances
                        self._update_balances_on_fill(order, fill_qty)
                        
                        # Log the fill
                        self.log_action("ORDER_FILLED", {
                            "order_id": order.order_id,
                            "market_id": order.market_id,
                            "side": order.side,
                            "price": str(order.filled_price),
                            "quantity": str(fill_qty),
                            "remaining_quantity": str(order.quantity - fill_qty)
                        })
                        
                        # Add to filled orders list
                        filled_orders.append(order)
                        
                        # If partially filled, update the order quantity
                        if fill_qty < order.quantity:
                            order.quantity -= fill_qty
                            order.filled = False  # Reset filled flag to allow further fills
                        else:
                            # Remove fully filled order
                            del self.orders[order_id]
                            
                        break  # Move to next order after filling this one
        
        # Check sell orders against current bids (if there's a matching bid at or above my ask price)
        for order_id, order in list(self.orders.items()):  # Use list() to avoid dict change during iteration
            if order.market_id != market_id:
                continue
                
            if order.side == 'sell' and not order.filled:
                # Check if any bid is at or above my ask price
                for bid in bids:
                    bid_price = Decimal(str(bid['price']))
                    bid_size = Decimal(str(bid['size']))
                    
                    if bid_price >= order.price:
                        # Fill the order
                        fill_qty = min(order.quantity, bid_size)
                        
                        # Update order status
                        order.filled = True
                        order.filled_at = time.time()
                        order.filled_price = bid_price
                        order.filled_quantity = fill_qty
                        
                        # Update balances
                        self._update_balances_on_fill(order, fill_qty)
                        
                        # Log the fill
                        self.log_action("ORDER_FILLED", {
                            "order_id": order.order_id,
                            "market_id": order.market_id,
                            "side": order.side,
                            "price": str(order.filled_price),
                            "quantity": str(fill_qty),
                            "remaining_quantity": str(order.quantity - fill_qty)
                        })
                        
                        # Add to filled orders list
                        filled_orders.append(order)
                        
                        # If partially filled, update the order quantity
                        if fill_qty < order.quantity:
                            order.quantity -= fill_qty
                            order.filled = False  # Reset filled flag to allow further fills
                        else:
                            # Remove fully filled order
                            del self.orders[order_id]
                            
                        break  # Move to next order after filling this one
        
        return filled_orders
    
    def _update_balances_on_fill(self, order: DryRunOrder, fill_qty: Decimal):
        """Update balances when an order is filled"""
        import logging
        logger = logging.getLogger(__name__)

        # Initialize balances for this market if not already done
        if order.market_id not in self.yes_balances:
            self.yes_balances[order.market_id] = Decimal('0')
        if order.market_id not in self.no_balances:
            self.no_balances[order.market_id] = Decimal('0')
        if order.market_id not in self.market_pnl:
            self.market_pnl[order.market_id] = Decimal('0')
        if order.market_id not in self.market_trades:
            self.market_trades[order.market_id] = 0

        # Track trade count
        self.market_trades[order.market_id] += 1

        # Calculate trade value
        trade_value = fill_qty * order.filled_price

        # For binary options on Polymarket, buying YES tokens or selling NO tokens affects balances differently
        if order.side == 'buy':
            # Buying - we spend USDC to acquire tokens
            self.yes_balances[order.market_id] += fill_qty
            self.usdc_balance -= trade_value
            # When buying, we're entering a position - no realized PnL yet
            logger.info(f"🟢 FILL: Bought {fill_qty:.2f} @ {order.filled_price:.4f} = ${trade_value:.2f}")
        elif order.side == 'sell':
            # Selling - we receive USDC and deliver tokens
            self.yes_balances[order.market_id] -= fill_qty
            self.usdc_balance += trade_value
            # When selling, we're closing a position - this is realized PnL
            # (simplified: assumes we bought at some average cost)
            logger.info(f"🔴 FILL: Sold {fill_qty:.2f} @ {order.filled_price:.4f} = ${trade_value:.2f}")

        # Save trade to database
        try:
            # Calculate fee (for now using a placeholder - in real implementation this would come from API)
            fee = Decimal('0')  # Placeholder - actual fees would come from the API response

            db_manager.save_trade(
                market_id=order.market_id,
                side=order.side,
                price=order.filled_price,
                size=fill_qty,
                fee=fee,
                tx_hash=f"DRY_RUN_FILL_{order.order_id}_{int(time.time())}"
            )
        except Exception as e:
            print(f"Error saving trade to database: {str(e)}")
    
    def get_orders(self, **filters) -> Dict[str, Any]:
        """Get list of orders (simulated)"""
        orders_list = []
        for order_id, order in self.orders.items():
            if filters:
                # Apply filters if provided
                match = True
                for key, value in filters.items():
                    if hasattr(order, key) and getattr(order, key) != value:
                        match = False
                        break
                if not match:
                    continue
            
            orders_list.append({
                "order_id": order.order_id,
                "market_id": order.market_id,
                "side": order.side,
                "price": str(order.price),
                "quantity": str(order.quantity),
                "status": "filled" if order.filled else "open",
                "placed_at": order.placed_at
            })
        
        return {
            "orders": orders_list,
            "count": len(orders_list)
        }
    
    def get_balances(self) -> Dict[str, Any]:
        """Get account balances (simulated)"""
        total_yes = sum(self.yes_balances.values())
        total_no = sum(self.no_balances.values())

        return {
            "usdc": float(self.usdc_balance),
            "usdc_balance": float(self.usdc_balance),
            "yes_tokens": {market: float(balance) for market, balance in self.yes_balances.items()},
            "no_tokens": {market: float(balance) for market, balance in self.no_balances.items()},
            "total_value_usd": float(self.usdc_balance + total_yes + total_no)  # Simplified calculation
        }

    def get_market_stats(self, market_id: str) -> Dict[str, Any]:
        """Get stats for a specific market"""
        return {
            "pnl": float(self.market_pnl.get(market_id, Decimal('0'))),
            "trades": self.market_trades.get(market_id, 0),
            "yes_balance": float(self.yes_balances.get(market_id, Decimal('0'))),
            "no_balance": float(self.no_balances.get(market_id, Decimal('0')))
        }

    def get_total_pnl(self) -> Dict[str, Any]:
        """Get total PnL across all markets"""
        total_realized = sum(self.market_pnl.values())
        total_trades = sum(self.market_trades.values())

        return {
            "realized_pnl": float(total_realized),
            "total_trades": total_trades,
            "fees_paid": float(self.total_fees_paid),
            "net_pnl": float(total_realized - self.total_fees_paid)
        }
    
    def record_pnl(self, market_id: str):
        """Record PnL at current time"""
        # For binary options on Polymarket, we need to consider the relationship:
        # price(YES) + price(NO) = $1.00
        # So if we hold YES and NO tokens, their combined value depends on resolution

        # For PnL calculation, we'll use a simplified approach:
        # - USDC balance is valued at face value
        # - YES/NO tokens are valued at current market prices if known, or at cost basis
        total_yes = self.yes_balances.get(market_id, Decimal('0'))
        total_no = self.no_balances.get(market_id, Decimal('0'))

        # For now, we'll use a simplified valuation - in reality, we'd need current market prices
        # to properly value the YES/NO tokens
        current_value = self.usdc_balance

        # Placeholder for more sophisticated valuation based on current market prices
        # This would require access to current mid-price for the market
        current_value += total_yes + total_no  # Simplified: assume tokens are worth 1 USDC each when held

        pnl = current_value - self.starting_balance

        pnl_record = PnLRecord(
            timestamp=time.time(),
            datetime=datetime.fromtimestamp(time.time()),
            market_id=market_id,
            pnl=pnl,
            yes_balance=total_yes,
            no_balance=total_no,
            usdc_balance=self.usdc_balance
        )

        self.pnl_records.append(pnl_record)

    def calculate_detailed_pnl(self, market_id: str, current_prices: Optional[Dict[str, Decimal]] = None) -> Dict[str, Decimal]:
        """
        Calculate more detailed PnL considering current market prices

        Args:
            market_id: The market to calculate PnL for
            current_prices: Current prices for YES/NO tokens {'yes_price': Decimal, 'no_price': Decimal}

        Returns:
            Dictionary with detailed PnL breakdown
        """
        yes_balance = self.yes_balances.get(market_id, Decimal('0'))
        no_balance = self.no_balances.get(market_id, Decimal('0'))

        # Calculate current value of holdings
        current_usdc_value = self.usdc_balance
        current_yes_value = Decimal('0')
        current_no_value = Decimal('0')

        if current_prices:
            current_yes_value = yes_balance * current_prices.get('yes_price', Decimal('0'))
            current_no_value = no_balance * current_prices.get('no_price', Decimal('0'))
        else:
            # Without current prices, use a simple approximation
            # In binary markets, if we don't know the current price, we might estimate based on mid-price
            # For now, we'll just return the basic calculation
            pass

        current_total_value = current_usdc_value + current_yes_value + current_no_value
        pnl = current_total_value - self.starting_balance

        return {
            'pnl': pnl,
            'usdc_value': current_usdc_value,
            'yes_value': current_yes_value,
            'no_value': current_no_value,
            'total_value': current_total_value,
            'yes_balance': yes_balance,
            'no_balance': no_balance
        }
    
    def generate_pnl_graph(self, output_file: str = "pnl_chart.png"):
        """Generate a PnL graph at the end of the session"""
        if not self.pnl_records:
            print("No PnL records to plot")
            return

        # Import visualization libraries
        plt, pd = _import_visualization_libs()

        # Convert to DataFrame for easier plotting
        df = pd.DataFrame([
            {
                'timestamp': record.timestamp,
                'datetime': record.datetime,
                'market_id': record.market_id,
                'pnl': float(record.pnl),
                'yes_balance': float(record.yes_balance),
                'no_balance': float(record.no_balance),
                'usdc_balance': float(record.usdc_balance)
            }
            for record in self.pnl_records
        ])

        # Create the plot
        plt.figure(figsize=(12, 8))

        # Plot PnL over time
        plt.subplot(2, 1, 1)
        plt.plot(df['datetime'], df['pnl'], label='PnL', linewidth=2)
        plt.title('Profit and Loss Over Time')
        plt.xlabel('Time')
        plt.ylabel('PnL (USD)')
        plt.legend()
        plt.grid(True)

        # Plot balances over time
        plt.subplot(2, 1, 2)
        plt.plot(df['datetime'], df['usdc_balance'], label='USDC Balance', linewidth=2)
        plt.plot(df['datetime'], df['yes_balance'], label='YES Tokens', linewidth=2)
        plt.plot(df['datetime'], df['no_balance'], label='NO Tokens', linewidth=2)
        plt.title('Balance Components Over Time')
        plt.xlabel('Time')
        plt.ylabel('Amount')
        plt.legend()
        plt.grid(True)

        # Adjust layout and save
        plt.tight_layout()
        plt.savefig(output_file)
        plt.show()

        print(f"PnL chart saved to {output_file}")

    def generate_detailed_report(self, output_file: str = "pnl_detailed_report.txt") -> str:
        """
        Generate a detailed PnL report at the end of the session

        Args:
            output_file: File to save the report to

        Returns:
            Report as a string
        """
        if not self.pnl_records:
            report = "No PnL records to report\n"
            with open(output_file, 'w') as f:
                f.write(report)
            return report

        # Calculate final stats
        final_pnl = self.pnl_records[-1].pnl
        total_orders_placed = len([log for log in self.logs if log['action'] == 'ORDER_PLACED'])
        total_orders_filled = len([log for log in self.logs if log['action'] == 'ORDER_FILLED'])
        total_orders_cancelled = len([log for log in self.logs if log['action'] == 'ORDER_CANCELLED'])

        report = f"""
POLYMARKET BOT DRY RUN REPORT
=============================

RUN SUMMARY
-----------
Start Time: {datetime.fromtimestamp(self.pnl_records[0].timestamp).strftime('%Y-%m-%d %H:%M:%S')}
End Time: {datetime.fromtimestamp(self.pnl_records[-1].timestamp).strftime('%Y-%m-%d %H:%M:%S')}
Duration: {(self.pnl_records[-1].timestamp - self.pnl_records[0].timestamp)/60:.2f} minutes

BALANCE SUMMARY
---------------
Starting Balance: ${float(self.starting_balance):,.2f}
Final USDC Balance: ${float(self.pnl_records[-1].usdc_balance):,.2f}
Final YES Balance: {float(self.pnl_records[-1].yes_balance):,.2f}
Final NO Balance: {float(self.pnl_records[-1].no_balance):,.2f}
Final Total Value: ${float(self.pnl_records[-1].usdc_balance + self.pnl_records[-1].yes_balance + self.pnl_records[-1].no_balance):,.2f}

PROFIT & LOSS
-------------
Net PnL: ${float(final_pnl):,.2f}
PnL Percentage: {(final_pnl / self.starting_balance * 100):.2f}%

TRADE STATISTICS
----------------
Orders Placed: {total_orders_placed}
Orders Filled: {total_orders_filled}
Orders Cancelled: {total_orders_cancelled}
Fill Rate: {(total_orders_filled / total_orders_placed * 100) if total_orders_placed > 0 else 0:.2f}%

LOG FILE
--------
Action logs saved to: {self.log_file}
        """

        with open(output_file, 'w') as f:
            f.write(report)

        return report
    
    def reset_simulation(self):
        """Reset the simulation state"""
        self.orders.clear()
        self.filled_orders.clear()
        self.pnl_records.clear()
        self.logs.clear()
        
        # Reset balances to starting values
        self.usdc_balance = self.starting_balance
        self.yes_balances.clear()
        self.no_balances.clear()
        
        # Clear the log file
        if Path(self.log_file).exists():
            Path(self.log_file).unlink()