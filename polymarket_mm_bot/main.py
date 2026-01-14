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
import time


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
        logger.info("Operating in DRY RUN mode - connecting to live Websockets but mocking execution layer")
    elif operation_mode == 'live':
        config.dry_run = False
        logger.warning("OPERATING IN LIVE MODE - REAL FUNDS WILL BE USED!")
        if not config.api_key or not config.secret_key or not config.wallet_address:
            logger.error("Missing required environment variables for live mode: POLYMARKET_API_KEY, POLYMARKET_SECRET_KEY, POLYMARKET_WALLET_ADDRESS")
            sys.exit(1)
    elif operation_mode == 'backtest':
        logger.info(f"Operating in BACKTEST mode - replaying historical data from {args.data or 'default historical data'}")
        # For backtesting, we would typically use a different execution path
        # This is a simplified implementation - in a real scenario, you'd load historical data
        config.dry_run = True  # Backtesting would also be a form of dry run

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

    logger.info(f"{'DRY RUN MODE' if config.dry_run else 'LIVE TRADING MODE'} - Initializing...")

    # If in dry run mode, initialize additional components
    if config.dry_run:
        logger.info(f"Dry run mode enabled. Logging to: {config.dry_run_log_file}")

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
    risk_manager = RiskManager(
        position_manager=position_manager,
        max_exposure=config_manager.get_max_exposure(),           # Max exposure from config
        kill_switch_threshold=config_manager.get_kill_switch_threshold(),  # Loss threshold from config
        fat_finger_threshold=config_manager.get_fat_finger_threshold(),   # Price deviation from config
        starting_balance=config.starting_balance  # Use config value
    )

    # Initialize the HFMM strategy
    strategy = HFMStrategy(
        position_manager=position_manager,
        target_spread=config_manager.get_target_spread(),  # Target spread from config
        min_order_size=config_manager.get_min_order_size(),
        max_order_size=config_manager.get_max_order_size(),
        num_levels=5
    )

    # Initialize the OrderManager with a 100ms tick interval and risk manager
    order_manager = OrderManager(
        rest_client=rest_client,
        tick_interval_ms=100,
        risk_manager=risk_manager
    )

    # Define market ID to track (this would be a real market ID from Polymarket)
    market_id = "Will Bitcoin hit $100k?"  # Example market ID

    # Register callbacks for different types of updates
    def on_order_book_update(local_book):
        logger.info(f"Order book updated for {local_book.market_id}")
        best_bid = local_book.get_best_bid()
        best_ask = local_book.get_best_ask()
        if best_bid and best_ask:
            logger.info(f"Best Bid: {best_bid.price} @ {best_bid.size}, Best Ask: {best_ask.price} @ {best_ask.size}")

            # Orders will be managed by the event loop, so we don't place them here directly

            # If in dry run mode, notify simulation engine of order book update
            if config.dry_run:
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

        # If in dry run mode, start the simulation engine
        if config.dry_run:
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

        # Keep the bot running
        last_pnl_snapshot_time = time.time()
        last_config_check_time = time.time()
        while True:
            await asyncio.sleep(1)

            # Check if the risk manager indicates immediate shutdown
            if risk_manager.should_shutdown_immediately():
                logger.critical("Risk manager triggered immediate shutdown!")
                break

            # Check for configuration updates every 30 seconds
            current_time = time.time()
            if current_time - last_config_check_time >= 30:  # 30 seconds
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

            # Record PnL snapshot every minute
            if current_time - last_pnl_snapshot_time >= 60:  # 60 seconds = 1 minute
                try:
                    # Calculate current balances and PnL
                    # For now, using mock values - in a real implementation these would come from the exchange
                    total_usdc = Decimal('10000')  # Placeholder - would come from exchange
                    total_positions_value = Decimal('500')  # Placeholder - would come from position manager

                    # Calculate cumulative PnL (starting balance - current total value)
                    current_total_value = total_usdc + total_positions_value
                    cumulative_pnl = current_total_value - config.starting_balance

                    # Record PnL snapshot
                    risk_manager.record_pnl_snapshot(
                        total_usdc=total_usdc,
                        total_positions_value=total_positions_value,
                        cumulative_pnl=cumulative_pnl
                    )

                    logger.info(f"PnL snapshot recorded: USDC=${total_usdc}, Positions=${total_positions_value}, PnL=${cumulative_pnl}")
                    last_pnl_snapshot_time = current_time
                except Exception as e:
                    logger.error(f"Error recording PnL snapshot: {str(e)}")

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