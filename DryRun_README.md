# Dry Run Mode for Polymarket MM Bot

The dry run mode allows you to test the market making bot without making real trades on Polymarket. Instead of sending real API requests, the bot will:

1. Log all 'Order Placed' and 'Order Cancelled' actions to a JSON file
2. Simulate fills based on real order book data (if the market price crosses your fake order price, it assumes the order was filled)
3. Update your fake inventory when orders are filled
4. Output a PnL (Profit and Loss) graph at the end of the session

## Configuration

To enable dry run mode, set the `DRY_RUN` environment variable to `true`:

```bash
export DRY_RUN=true
export DRY_RUN_LOG_FILE="my_dry_run_log.json"
export STARTING_BALANCE=10000
```

Or you can set these values directly in the config:

```python
config = PolymarketConfig(
    api_key="your_api_key",
    secret_key="your_secret_key", 
    wallet_address="your_wallet",
    dry_run=True,
    dry_run_log_file="dry_run_log.json",
    starting_balance=Decimal('10000')
)
```

## Running in Dry Run Mode

To run the bot in dry run mode:

```bash
# Set environment variables
export DRY_RUN=true
export POLYMARKET_API_KEY=your_api_key
export POLYMARKET_SECRET_KEY=your_secret_key
export POLYMARKET_WALLET_ADDRESS=your_wallet

# Run the bot
python -m polymarket_mm_bot.main
```

## Files Generated in Dry Run Mode

When running in dry run mode, the bot will generate the following files:

- `dry_run_log.json` - Contains all logged actions (can be customized with DRY_RUN_LOG_FILE)
- `pnl_chart.png` - Profit and loss chart showing performance over time
- `pnl_detailed_report.txt` - Detailed report with statistics about the dry run session

## Key Features

- **Safe Testing**: No real money is at risk during testing
- **Realistic Simulation**: Uses actual order book data to simulate fills
- **Comprehensive Logging**: All actions are recorded for analysis
- **Performance Tracking**: PnL tracking and reporting to evaluate strategy performance
- **Easy Switching**: Toggle between live and dry run modes with a single configuration change

## Binary Market Considerations

Remember that for binary options on Polymarket:
- `price(YES) + price(NO) = $1.00` (approximately)
- Use this parity to calculate the fair price of illiquid sides
- All web3 interactions are configured for the Polygon (MATIC) PoS chain
- The CTF exchange (mint/redeem) is separate from the CLOB (trading)