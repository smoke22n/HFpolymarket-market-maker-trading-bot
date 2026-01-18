# Polymarket Market Maker Bot

A high-frequency market maker bot for Polymarket's CLOB (Central Limit Order Book) with automatic market discovery and smart order management.

## Quick Start

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run in dry-run mode (safe testing with real market data)
python -m polymarket_mm_bot.main --dry-run
```

## Features

### 🔍 Auto Market Discovery
Automatically discovers and trades the highest volume markets from Polymarket's API:
- Filters by minimum volume, liquidity, and spread
- Hourly refresh to add/remove markets dynamically
- Cancels orders for markets that no longer meet criteria

```bash
# Trade top 5 markets with $500k+ volume, refresh every 30 min
python -m polymarket_mm_bot.main --dry-run --min-volume 500000 --max-markets 5 --refresh-interval 1800
```

### 📊 Smart Order Management
- **10-second cooldown** between order replacements (no spam)
- **1.5-second tick interval** for order book checks
- **50 bps threshold** for price changes to trigger requote
- **30-second stale order refresh**
- Orders rest on the book to actually get filled

### 💰 PnL Tracking
- Per-market realized PnL and trade counts
- Cumulative PnL across all markets
- Live stats in heartbeat logs every 10 seconds
- End-of-session PnL chart and detailed report

### 🛡️ Risk Management
- **Max Exposure Guard**: Limits total inventory exposure
- **Kill Switch**: Auto-shutdown on excessive losses
- **Fat Finger Protection**: Prevents erroneous pricing

## Command Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `--dry-run` | enabled | Simulate trading with real market data |
| `--live` | - | Real trading mode (USE WITH CAUTION) |
| `--min-volume` | 100000 | Minimum market volume in USD |
| `--max-markets` | 10 | Maximum number of markets to trade |
| `--refresh-interval` | 3600 | Market refresh interval in seconds |
| `--data` | - | Historical data file for backtesting |

## Example Output

```
🔍 Discovering markets (min vol: $100,000, max: 10)...
================================================================================
🔍 DISCOVERED HIGH-VOLUME MARKETS
================================================================================

 1. Will the Buffalo Bills win Super Bowl 2026?
    📊 Volume: $5.5B | 💧 Liquidity: $892K | 📈 YES: 12.3%

 2. Will GTA 6 cost $100+?
    📊 Volume: $1.3B | 💧 Liquidity: $156K | 📈 YES: 65.0%

✅ Discovered 20 token pairs from 10 markets
🎯 OrderManager started (tick: 1500ms, cooldown: 10.0s)
⏰ Market refresh task started (every 60 min)

💓 🟢 WS | 📊 10/10 mkts | 💼 100 orders | 🔄 5 fills | 📈 $+12.50 PnL | 💰 $10012.50
   📌 Bills SB Y: Mid 0.1230 | Spread 25bps | Trades 2 | PnL $+5.00
   📌 GTA6 $100 Y: Mid 0.6500 | Spread 30bps | Trades 3 | PnL $+7.50
```

## Configuration

### Environment Variables

Create a `.env` file:
```bash
DRY_RUN=true
POLYMARKET_API_KEY=your_api_key
POLYMARKET_SECRET_KEY=your_secret_key
POLYMARKET_WALLET_ADDRESS=0x...
STARTING_BALANCE=10000
```

### Strategy Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `target_spread` | 20 bps | Target bid-ask spread |
| `min_order_size` | 10 | Minimum order size |
| `max_order_size` | 1000 | Maximum order size |
| `num_levels` | 5 | Price levels per side |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Main Event Loop                         │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │   Market     │  │    Order     │  │     Market       │  │
│  │  Discovery   │──│   Manager    │──│   Data Engine    │  │
│  │  (hourly)    │  │  (1.5s tick) │  │   (WebSocket)    │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│         │                 │                   │             │
│         ▼                 ▼                   ▼             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  Polymarket  │  │    HFMM      │  │   Local Order    │  │
│  │  Gamma API   │  │   Strategy   │  │     Books        │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Module Structure

- `api/` - REST and WebSocket clients, connection management
- `market_data/` - Order book engine, market data ingestion
- `strategies/` - HFMM strategy, order generation
- `utils/` - Market discovery, order manager, risk manager, PnL tracking
- `config/` - Configuration and settings

## Operation Modes

### Dry Run Mode (`--dry-run`)
Connects to live WebSocket for real market data but simulates order execution:
- Real-time order book data
- Simulated fills based on order book crosses
- Trade log saved to `dry_run_log.json`
- PnL chart generated at end of session

```bash
python -m polymarket_mm_bot.main --dry-run
```

### Live Mode (`--live`)
⚠️ **WARNING: Real funds will be used!**

```bash
python -m polymarket_mm_bot.main --live
```

### Backtest Mode (`--backtest`)
Replay historical data to simulate trading performance:

```bash
python -m polymarket_mm_bot.main --backtest --data ./history/data.csv
```

## Risk Management

```python
risk_manager = RiskManager(
    position_manager=position_manager,
    max_exposure=Decimal('1000'),           # Max $1000 exposure
    kill_switch_threshold=Decimal('0.10'),  # 10% loss threshold
    fat_finger_threshold=Decimal('0.05'),   # 5% price deviation
    starting_balance=Decimal('10000')
)
```

## API Clients

### REST Client
- `get_markets()` - Fetch all markets
- `get_orderbook(market_id)` - Get order book
- `place_order(params)` - Place order
- `cancel_order(order_id)` - Cancel order
- `get_balances()` - Get account balances

### WebSocket Client
- Real-time order book streaming
- Auto-reconnect with heartbeat
- Handler-based message processing

## Rate Limiting

Implements sliding window rate limiter for Polymarket's API limits (500 requests/10 seconds).

## License

MIT
