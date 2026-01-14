"""
Test script to verify the database functionality for the Polymarket bot
"""
import asyncio
from decimal import Decimal
from polymarket_mm_bot.utils.database import db_manager
from polymarket_mm_bot.utils.config_manager import config_manager


def test_database_operations():
    """Test all database operations"""
    print("Testing database operations...")
    
    # Test saving a trade
    print("\n1. Testing Trade creation...")
    trade = db_manager.save_trade(
        market_id="test_market_123",
        side="buy",
        price=Decimal('0.5500'),
        size=Decimal('100'),
        fee=Decimal('0.10'),
        tx_hash="0x123456789abcdef"
    )
    print(f"Saved trade: {trade}")
    
    # Test saving a PnL snapshot
    print("\n2. Testing PnL Snapshot creation...")
    snapshot = db_manager.save_pnl_snapshot(
        total_usdc=Decimal('10000'),
        total_positions_value=Decimal('500'),
        cumulative_pnl=Decimal('100')
    )
    print(f"Saved PnL snapshot: {snapshot}")
    
    # Test saving an active order
    print("\n3. Testing Active Order creation...")
    order = db_manager.save_active_order(
        order_id="test_order_456",
        market_id="test_market_123",
        side="sell",
        price=Decimal('0.5600'),
        size=Decimal('50'),
        status="open"
    )
    print(f"Saved active order: {order}")
    
    # Test updating order status
    print("\n4. Testing Order Status Update...")
    updated_order = db_manager.update_order_status("test_order_456", "filled")
    print(f"Updated order status: {updated_order}")
    
    # Test saving bot config
    print("\n5. Testing Bot Config creation/update...")
    config = db_manager.save_bot_config(
        param_name="test_param",
        param_value="test_value",
        description="Test parameter for validation"
    )
    print(f"Saved bot config: {config}")
    
    # Test getting bot config
    print("\n6. Testing Bot Config retrieval...")
    retrieved_config = db_manager.get_bot_config("test_param")
    print(f"Retrieved bot config: {retrieved_config}")
    
    # Test getting all bot configs
    print("\n7. Testing All Bot Configs retrieval...")
    all_configs = db_manager.get_all_bot_configs()
    print(f"All bot configs: {len(all_configs)} found")
    for config in all_configs:
        print(f"  - {config.param_name}: {config.param_value}")
    
    # Test getting active orders
    print("\n8. Testing Active Orders retrieval...")
    active_orders = db_manager.get_active_orders("test_market_123")
    print(f"Active orders for test_market_123: {len(active_orders)} found")
    for order in active_orders:
        print(f"  - {order.order_id}: {order.side} {order.size} @ {order.price}")
    
    print("\nDatabase operations test completed successfully!")


def test_config_manager():
    """Test the config manager functionality"""
    print("\n\nTesting Config Manager...")
    
    # Test getting default values
    print(f"Target spread: {config_manager.get_target_spread()}")
    print(f"Max exposure: {config_manager.get_max_exposure()}")
    print(f"Min order size: {config_manager.get_min_order_size()}")
    print(f"Max order size: {config_manager.get_max_order_size()}")
    print(f"Kill switch threshold: {config_manager.get_kill_switch_threshold()}")
    print(f"Fat finger threshold: {config_manager.get_fat_finger_threshold()}")
    
    # Test updating a value
    print("\nUpdating target spread to 0.0030...")
    success = config_manager.set_target_spread(Decimal('0.0030'))
    print(f"Update successful: {success}")
    print(f"New target spread: {config_manager.get_target_spread()}")
    
    print("\nConfig Manager test completed successfully!")


if __name__ == "__main__":
    test_database_operations()
    test_config_manager()
    
    print("\n\nAll tests completed! Check the SQLite database file 'polymarket_bot.db' for stored data.")