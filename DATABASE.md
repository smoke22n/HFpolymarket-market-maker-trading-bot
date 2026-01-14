# Database Architecture

## Overview

The trading bot uses SQLite as its primary data store for persisting trading state, historical trades, orders, and PnL calculations. The database serves as the single source of truth for the bot's state and enables reliable recovery after restarts.

## Schema Definitions

### Trades Table
Stores all executed trades for historical analysis and PnL calculation.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER (PRIMARY KEY) | Unique identifier for each trade |
| market_id | TEXT | Identifier for the market being traded |
| outcome | TEXT | The outcome being traded (YES/NO) |
| side | TEXT | Trade direction (BUY/SELL) |
| quantity | REAL | Number of tokens traded |
| price | REAL | Price at which the trade was executed |
| timestamp | DATETIME | Time when the trade was executed |
| fee | REAL | Transaction fees paid |
| order_id | TEXT | Associated order ID |
| pnl | REAL | Profit/Loss from this trade |

### Orders Table
Tracks all orders placed by the bot, including both active and filled orders.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER (PRIMARY KEY) | Unique identifier for each order |
| order_id | TEXT | External order ID from exchange |
| market_id | TEXT | Identifier for the market being traded |
| outcome | TEXT | The outcome being traded (YES/NO) |
| side | TEXT | Order direction (BUY/SELL) |
| quantity | REAL | Quantity of tokens to trade |
| price | REAL | Limit price for the order |
| status | TEXT | Current status (PENDING/FILLED/CANCELLED/REJECTED) |
| created_at | DATETIME | Time when order was placed |
| filled_at | DATETIME | Time when order was filled (NULL if not filled) |
| filled_quantity | REAL | Quantity that has been filled |
| average_fill_price | REAL | Average price at which order was filled |

### PnL Table
Aggregates profit and loss data for reporting and monitoring.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER (PRIMARY KEY) | Unique identifier for each PnL record |
| market_id | TEXT | Identifier for the market |
| date | DATE | Date for the PnL aggregation |
| realized_pnl | REAL | Realized profit and loss for the day |
| unrealized_pnl | REAL | Unrealized profit and loss based on current positions |
| total_pnl | REAL | Sum of realized and unrealized PnL |
| fees_paid | REAL | Total fees paid during the period |
| volume_traded | REAL | Total volume traded during the period |

## State Management & Recovery

### Initialization Process
When the bot starts up, it follows this sequence to restore its state:

1. **Database Connection**: Establishes connection to the SQLite database
2. **Schema Verification**: Ensures all required tables exist and are properly structured
3. **Active Orders Sync**: Queries the exchange API to retrieve current open orders and reconciles with local records
4. **Position Calculation**: Recalculates current positions based on all historical trades
5. **Risk Parameter Reset**: Restores risk parameters to safe values during initialization

### Reconciliation Process
The reconciliation process ensures the bot's internal state matches the exchange state:

1. **Fetch Open Orders**: Retrieves all open orders from the exchange API
2. **Compare with Local State**: Matches exchange orders with local order records
3. **Update Status**: Updates local order status for any discrepancies
4. **Cancel Orphaned Orders**: Cancels any local orders that don't exist on the exchange
5. **Restore Missing Orders**: Creates local records for any exchange orders not in local database

### Recovery Scenarios

#### Graceful Restart
- Reads all unfilled orders from database
- Confirms their existence on the exchange
- Resumes normal operations with current positions and risk metrics

#### Crash Recovery
- Performs full reconciliation with exchange
- Identifies any executed trades not recorded in the database
- Updates position calculations based on confirmed exchange state
- Applies conservative risk adjustments during recovery period

#### Network Disruption Recovery
- Detects when connection was lost and duration
- Synchronizes all missed trades/orders when connection resumes
- Validates that no orders were filled during disconnection
- Recalculates positions and adjusts strategies accordingly