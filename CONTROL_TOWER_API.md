# Control Tower API for Polymarket Market Maker Bot

The Control Tower API provides a REST interface to monitor and control the high-frequency trading bot. It runs as a FastAPI server that wraps the trading bot functionality.

## Features

- **Background Task Runner**: The HFT loop runs independently of the API server
- **Real-time Statistics**: Monitor PnL, Open Exposure, and Win/Loss ratio
- **Transaction History**: Paginated access to completed transactions
- **Remote Control**: Pause, Resume, or Panic Sell (liquidate all positions)
- **Dynamic Configuration**: Update spread or bet size without restarting

## Endpoints

### GET `/stats`

Returns current trading statistics including:
- PnL (Profit and Loss)
- Open Exposure
- Win/Loss ratio
- Total trades
- Bot state
- Timestamp

**Example Response:**
```json
{
  "pnl": 101.25,
  "open_exposure": 0.0,
  "win_loss_ratio": 0.0,
  "total_trades": 0,
  "bot_state": "stopped",
  "timestamp": "2026-01-14T00:44:34.135162"
}
```

### GET `/history`

Returns a paginated list of completed transactions.

**Query Parameters:**
- `page` (int, default: 1): Page number
- `page_size` (int, default: 10, max: 100): Number of items per page
- `market_id` (string, optional): Filter by market ID

**Example Response:**
```json
{
  "trades": [
    {
      "id": 1,
      "timestamp": "2026-01-14T00:33:19.512940",
      "market_id": "test_market_123",
      "side": "buy",
      "price": 0.55,
      "size": 100.0,
      "fee": 0.1,
      "tx_hash": "0x123456789abcdef"
    }
  ],
  "total_count": 1,
  "page": 1,
  "page_size": 10
}
```

### POST `/control`

Controls the bot state: Pause, Resume, or Panic Sell.

**Request Body:**
```json
{
  "action": "pause" // Options: "pause", "resume", "panic_sell"
}
```

**Example Response:**
```json
{
  "action": "pause",
  "success": true,
  "message": "Bot paused successfully",
  "timestamp": "2026-01-14T00:45:10.957606"
}
```

### POST `/config`

Updates bot configuration parameters dynamically.

**Request Body:**
```json
{
  "param_name": "target_spread",
  "param_value": "0.0030",
  "description": "Optional description"
}
```

Supported parameters:
- `target_spread`: Target spread for market making
- `max_exposure`: Maximum exposure per market
- `min_order_size`: Minimum order size
- `max_order_size`: Maximum order size
- `kill_switch_threshold`: Kill switch threshold (percentage)
- `fat_finger_threshold`: Fat finger check threshold (percentage)

**Example Response:**
```json
{
  "param_name": "target_spread",
  "param_value": "0.0030",
  "success": true,
  "message": "Configuration 'target_spread' updated to '0.0030'",
  "timestamp": "2026-01-14T00:45:31.166289"
}
```

## Running the Server

### Prerequisites

Make sure you have the required dependencies installed:

```bash
pip install -r requirements.txt
pip install fastapi uvicorn
```

### Starting the Server

```bash
python control_tower_server.py --host 0.0.0.0 --port 8000
```

Or directly with uvicorn:

```bash
uvicorn polymarket_mm_bot.control_tower.api_server:app --host 0.0.0.0 --port 8000
```

The server will be available at `http://localhost:8000`

## Architecture

The Control Tower consists of:

1. **BackgroundRunner**: Manages the trading bot lifecycle independently of the API server
2. **FastAPI Server**: Provides REST endpoints for monitoring and control
3. **Database Integration**: Uses the existing database layer for persistent data
4. **Configuration Manager**: Allows dynamic updates to bot parameters