# Polymarket Bot - Database Persistence Layer

## Overview

The Polymarket Market Maker Bot now includes a comprehensive database persistence layer using SQLite and SQLAlchemy. This enables the bot to:

1. Store executed trades for performance tracking
2. Record PnL snapshots for equity monitoring
3. Maintain active orders in sync with memory
4. Store and update bot configuration parameters dynamically

## Database Schema

The database includes four main tables:

### 1. Trades Table
Stores all executed fills with the following fields:
- `id`: Auto-incrementing primary key
- `timestamp`: When the trade was executed (UTC)
- `market_id`: Identifier for the market
- `side`: Buy or sell
- `price`: Execution price
- `size`: Quantity traded
- `fee`: Transaction fee (if available)
- `tx_hash`: Transaction hash from blockchain

### 2. PnL Snapshots Table
Records equity snapshots every minute with:
- `id`: Auto-incrementing primary key
- `timestamp`: When the snapshot was taken (UTC)
- `total_usdc`: Total USDC balance
- `total_positions_value`: Total value of all positions
- `cumulative_pnl`: Cumulative profit and loss

### 3. Active Orders Table
Syncs with the bot's memory to track live orders:
- `id`: Auto-incrementing primary key
- `order_id`: Unique order identifier
- `market_id`: Market identifier
- `side`: Buy or sell
- `price`: Order price
- `size`: Order size
- `status`: Order status (open, filled, cancelled, partially_filled)
- `created_at`: When the order was created
- `updated_at`: When the order was last updated

### 4. Bot Config Table
Stores configurable parameters that can be changed without restarting:
- `id`: Auto-incrementing primary key
- `param_name`: Configuration parameter name
- `param_value`: Current value of the parameter
- `description`: Description of the parameter
- `updated_at`: When the parameter was last updated

## Key Features

### Dynamic Configuration Updates
The bot now supports runtime configuration updates through the database:

- `target_spread`: Target spread for market making (default: 0.0020 / 20 bps)
- `max_exposure`: Maximum exposure per market (default: $1000)
- `min_order_size`: Minimum order size (default: 10)
- `max_order_size`: Maximum order size (default: 1000)
- `kill_switch_threshold`: Kill switch threshold (default: 0.10 / 10% loss)
- `fat_finger_threshold`: Fat finger check threshold (default: 0.05 / 5% deviation)

### Automatic Data Recording
- Trades are automatically saved when executed (both in live and dry-run modes)
- PnL snapshots are recorded every minute
- Active orders are synchronized with the database in real-time
- Order status updates are reflected in the database

## Usage

### Accessing Data
The database can be accessed directly using SQLite tools or programmatically through the `DatabaseManager` class:

```python
from polymarket_mm_bot.utils.database import db_manager

# Get all active orders for a market
active_orders = db_manager.get_active_orders("market_id_here")

# Get all bot configurations
configs = db_manager.get_all_bot_configs()

# Save a manual trade
db_manager.save_trade(
    market_id="test_market",
    side="buy",
    price=Decimal('0.50'),
    size=Decimal('100'),
    fee=Decimal('0.10'),
    tx_hash="0x..."
)
```

### Updating Configuration
Configuration parameters can be updated dynamically:

```python
from polymarket_mm_bot.utils.config_manager import config_manager

# Update target spread
config_manager.set_target_spread(Decimal('0.0030'))

# Update max exposure
config_manager.set_max_exposure(Decimal('2000'))
```

## Integration Points

The database layer is integrated into the following components:

1. **OrderManager**: Saves and updates active orders
2. **DryRunMode**: Saves executed trades during simulation
3. **RiskManager**: Records PnL snapshots
4. **Main Loop**: Checks for configuration updates periodically
5. **ConfigManager**: Manages dynamic configuration parameters

## Database File Location

By default, the database is stored as `polymarket_bot.db` in the project root directory. This can be changed by modifying the database path in the `DatabaseManager` initialization.

## Future Scalability

While currently using SQLite for simplicity, the architecture supports migration to PostgreSQL by changing the database URL in the `DatabaseManager` class. The SQLAlchemy ORM ensures compatibility across different database systems.