#!/usr/bin/env python3
"""
Test script for Dry Run Mode functionality
"""
import asyncio
import os
from decimal import Decimal
from polymarket_mm_bot.utils.dry_run import DryRunMode
from polymarket_mm_bot.api.client import PolymarketRestClient, Credentials
from polymarket_mm_bot.config.settings import PolymarketConfig


async def test_dry_run_basic():
    """Test basic dry run functionality"""
    print("Testing basic dry run functionality...")

    # Create dry run mode instance
    dry_run = DryRunMode(log_file="test_dry_run_log.json", starting_balance=Decimal('1000'))

    # Test placing an order
    order_params = {
        'marketId': 'test_market',
        'side': 'buy',
        'price': '0.45',
        'quantity': '10',
        'type': 'limit'
    }

    result = dry_run.place_order(order_params)
    print(f"Place order result: {result}")

    # Test getting orders
    orders_result = dry_run.get_orders()
    print(f"Get orders result: {orders_result}")

    # Test getting balances
    balances = dry_run.get_balances()
    print(f"Balances: {balances}")

    # Test cancelling an order
    if 'order_id' in result:
        cancel_result = dry_run.cancel_order(result['order_id'])
        print(f"Cancel order result: {cancel_result}")

    print("Basic dry run functionality test completed.\n")


async def test_dry_run_with_rest_client():
    """Test dry run mode integrated with REST client"""
    print("Testing dry run with REST client...")

    # Create a dummy config and credentials for testing
    config = PolymarketConfig(
        api_key="dummy",
        secret_key="dummy",
        wallet_address="dummy",
        dry_run=True
    )

    credentials = Credentials(
        api_key="dummy",
        secret_key="dummy",
        wallet_address="dummy"
    )

    # Initialize REST client in dry run mode
    rest_client = PolymarketRestClient(credentials, config.base_url, dry_run=True)

    # Test placing an order through the client
    order_params = {
        'marketId': 'test_market_2',
        'side': 'sell',
        'price': '0.55',
        'quantity': '20',
        'type': 'limit'
    }

    result = await rest_client.place_order(order_params)
    print(f"Place order via client result: {result}")

    # Test getting balances
    balances = await rest_client.get_balances()
    print(f"Balances via client: {balances}")

    # Test cancelling an order
    if 'order_id' in result:
        cancel_result = await rest_client.cancel_order(result['order_id'])
        print(f"Cancel order via client result: {cancel_result}")

    print("Dry run with REST client test completed.\n")


async def test_order_fill_simulation():
    """Test order fill simulation"""
    print("Testing order fill simulation...")

    # Create dry run mode
    dry_run = DryRunMode(log_file="test_fill_simulation.json", starting_balance=Decimal('1000'))

    # Place a buy order
    buy_order_params = {
        'marketId': 'fill_test_market',
        'side': 'buy',
        'price': '0.40',
        'quantity': '10',
        'type': 'limit'
    }
    buy_result = dry_run.place_order(buy_order_params)
    print(f"Buy order placed: {buy_result}")

    # Place a sell order
    sell_order_params = {
        'marketId': 'fill_test_market',
        'side': 'sell',
        'price': '0.60',
        'quantity': '15',
        'type': 'limit'
    }
    sell_result = dry_run.place_order(sell_order_params)
    print(f"Sell order placed: {sell_result}")

    # Create a simulated order book where the sell order should match the buy order
    # Our buy order is at 0.40, so if the market has asks at 0.40 or below, it should fill
    current_order_book = {
        'bids': [
            {'price': '0.42', 'size': '5'},
            {'price': '0.40', 'size': '8'},  # This should match our buy order at 0.40
        ],
        'asks': [
            {'price': '0.58', 'size': '6'},
            {'price': '0.60', 'size': '12'},  # This should match our sell order at 0.60
        ]
    }

    # Simulate fills
    filled_orders = dry_run.simulate_fills('fill_test_market', current_order_book)
    print(f"Filled orders: {len(filled_orders)}")

    for order in filled_orders:
        print(f"  Filled order {order.order_id}: {order.side} {order.filled_quantity} @ {order.filled_price}")

    # Check balances after fills
    balances = dry_run.get_balances()
    print(f"Balances after fills: {balances}")

    print("Order fill simulation test completed.\n")


async def main():
    """Run all tests"""
    print("Running Dry Run Mode tests...\n")

    await test_dry_run_basic()
    await test_dry_run_with_rest_client()
    await test_order_fill_simulation()

    print("All tests completed!")


if __name__ == "__main__":
    asyncio.run(main())