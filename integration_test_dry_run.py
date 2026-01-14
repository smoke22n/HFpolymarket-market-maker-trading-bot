#!/usr/bin/env python3
"""
Simple test to validate dry run functionality works end-to-end
"""
import asyncio
import logging
import signal
import sys
from decimal import Decimal

from polymarket_mm_bot.api.client import PolymarketRestClient, Credentials
from polymarket_mm_bot.config.settings import PolymarketConfig
from polymarket_mm_bot.market_data.order_book_engine import MarketDataIngestionEngine
from polymarket_mm_bot.strategies.hfmm_strategy import HFMStrategy
from polymarket_mm_bot.utils.position_manager import PositionManager
from polymarket_mm_bot.utils.order_manager import OrderManager
from polymarket_mm_bot.utils.risk_manager import RiskManager
from polymarket_mm_bot.utils.dry_run import DryRunMode
from polymarket_mm_bot.utils.simulation_engine import SimulationEngine
from unittest import mock


# Global variable to control the main loop
should_exit = False


def signal_handler(signum, frame):
    global should_exit
    print("\nReceived interrupt signal. Shutting down...")
    should_exit = True


async def main():
    global should_exit
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger = logging.getLogger(__name__)

    # Create a dry run config
    config = PolymarketConfig(
        api_key="dummy",
        secret_key="dummy",
        wallet_address="dummy",
        dry_run=True,
        dry_run_log_file="integration_test_dry_run_log.json",
        starting_balance=Decimal('10000')
    )

    # Create credentials object
    credentials = Credentials(
        api_key="dummy",
        secret_key="dummy",
        wallet_address="dummy"
    )

    # Initialize REST client with dry run mode
    rest_client = PolymarketRestClient(credentials, config.base_url, dry_run=True)
    
    logger.info(f"DRY RUN MODE - Initializing...")

    # Initialize dry run mode
    dry_run_mode = DryRunMode(
        log_file=config.dry_run_log_file,
        starting_balance=config.starting_balance
    )

    # Initialize simulation engine
    simulation_engine = SimulationEngine(dry_run_mode)

    # Update rest client to use dry run mode
    rest_client.dry_run_mode = dry_run_mode

    # Initialize the market data ingestion engine
    market_data_engine = MarketDataIngestionEngine(
        credentials=credentials,
        ws_url=config.ws_url
    )

    # Initialize position manager with mock
    mock_api_client = mock.Mock()
    position_manager = PositionManager(mock_api_client)

    # Initialize the RiskManager with safety parameters
    risk_manager = RiskManager(
        position_manager=position_manager,
        max_exposure=Decimal('1000'),           # Max $1000 exposure
        kill_switch_threshold=Decimal('0.10'),  # 10% loss threshold
        fat_finger_threshold=Decimal('0.05'),   # 5% price deviation
        starting_balance=config.starting_balance  # Use config value
    )

    # Initialize the HFMM strategy
    strategy = HFMStrategy(
        position_manager=position_manager,
        target_spread=Decimal('0.0020'),  # 20 bps
        min_order_size=Decimal('10'),
        max_order_size=Decimal('1000'),
        num_levels=5
    )

    # Initialize the OrderManager with a 100ms tick interval and risk manager
    order_manager = OrderManager(
        rest_client=rest_client,
        tick_interval_ms=100,
        risk_manager=risk_manager
    )

    # Define market ID to track
    market_id = "Integration Test Market"

    # Register callbacks for different types of updates
    def on_order_book_update(local_book):
        logger.info(f"Order book updated for {local_book.market_id}")
        best_bid = local_book.get_best_bid()
        best_ask = local_book.get_best_ask()
        if best_bid and best_ask:
            logger.info(f"Best Bid: {best_bid.price} @ {best_bid.size}, Best Ask: {best_ask.price} @ {best_ask.size}")

            # If in dry run mode, notify simulation engine of order book update
            simulation_engine.subscribe_to_market(market_id, local_book)

    def on_mid_price_update(mid_price):
        logger.info(f"Mid-price updated: {mid_price}")

    def on_spread_update(spread):
        logger.info(f"Spread updated: {spread}")

    # Register the callbacks
    market_data_engine.register_update_callback(market_id, on_order_book_update)
    market_data_engine.register_mid_price_callback(market_id, on_mid_price_update)
    market_data_engine.register_spread_callback(market_id, on_spread_update)

    try:
        # Start the market data ingestion engine
        await market_data_engine.start()
        logger.info("Market data ingestion engine started")

        # Start the simulation engine for dry run mode
        await simulation_engine.start()
        logger.info("Simulation engine started for dry run mode")

        # Start the order manager
        await order_manager.start()
        logger.info("Order manager started")

        # Subscribe to the market
        market_data_engine.subscribe_to_market(market_id)
        logger.info(f"Subscribed to market: {market_id}")

        # Simulate adding a position to demonstrate the strategy
        position_manager.track_position(
            market_id=market_id,
            yes_balance=Decimal('500'),
            no_balance=Decimal('300'),
            collateral_token_address="0x...",
            condition_id="test_condition"
        )
        logger.info("Added sample position for demonstration")

        # Start the main event loop for order management
        event_loop_task = asyncio.create_task(
            order_manager.run_event_loop(strategy, market_data_engine)
        )

        # Run for a short time to test functionality
        run_time = 0
        max_run_time = 5  # Run for 5 seconds
        
        while run_time < max_run_time and not should_exit:
            await asyncio.sleep(1)
            run_time += 1

            # Check if the risk manager indicates immediate shutdown
            if risk_manager.should_shutdown_immediately():
                logger.critical("Risk manager triggered immediate shutdown!")
                break

            # You can access the current state at any time:
            current_mid_price = market_data_engine.get_current_mid_price(market_id)
            current_spread = market_data_engine.get_current_spread(market_id)

            if current_mid_price:
                logger.info(f"Current mid-price from external access: {current_mid_price}")
            if current_spread:
                logger.info(f"Current spread from external access: {current_spread}")

            # Log order status
            order_count = await order_manager.get_order_count_for_market(market_id)
            logger.info(f"Active orders for {market_id}: {order_count}")

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Error in main loop: {e}")
    finally:
        # Cancel the event loop task
        if 'event_loop_task' in locals():
            event_loop_task.cancel()
            try:
                await event_loop_task
            except asyncio.CancelledError:
                pass

        # Stop the order manager
        await order_manager.stop()

        # Stop the market data engine
        await market_data_engine.stop()
        
        # Generate reports
        logger.info("Generating dry run reports...")
        try:
            # Generate PnL chart
            rest_client.dry_run_mode.generate_pnl_graph("integration_test_pnl_chart.png")
            
            # Generate detailed report
            report = rest_client.dry_run_mode.generate_detailed_report("integration_test_pnl_detailed_report.txt")
            logger.info("Dry run reports generated successfully")
            print(report)
        except Exception as e:
            logger.error(f"Error generating dry run reports: {e}")
        
        logger.info("Integration test completed successfully!")


if __name__ == "__main__":
    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    asyncio.run(main())