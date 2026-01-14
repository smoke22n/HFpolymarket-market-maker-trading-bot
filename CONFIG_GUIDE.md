# Configuration Guide

This guide documents all configuration parameters for the Polymarket Market Maker Bot. Parameters are organized by category and include their description, default value, and impact on trading behavior.

## Environment Variables

### API Configuration
| Parameter | Description | Default Value | Impact |
|-----------|-------------|---------------|---------|
| `POLYMARKET_API_KEY` | Your Polymarket API key for authentication | (required) | Enables API access to Polymarket's CLOB |
| `POLYMARKET_SECRET_KEY` | Your Polymarket secret key for authentication | (required) | Required for secure API communication |
| `POLYMARKET_WALLET_ADDRESS` | Your Polygon wallet address | (required) | Identifies your trading account |

### API Endpoint Configuration
| Parameter | Description | Default Value | Impact |
|-----------|-------------|---------------|---------|
| `POLYMARKET_BASE_URL` | REST API base URL | `https://clob.polymarket.com` | Determines which Polymarket REST API endpoint to use |
| `POLYMARKET_WS_URL` | WebSocket API URL | `wss://clob.polymarket.com/ws` | Determines which Polymarket WebSocket endpoint to connect to |

### Rate Limiting Configuration
| Parameter | Description | Default Value | Impact |
|-----------|-------------|---------------|---------|
| `RATE_LIMIT_MAX_REQUESTS` | Maximum requests per time window | `500` | Controls API request frequency to comply with Polymarket limits |
| `RATE_LIMIT_TIME_WINDOW` | Time window in seconds for rate limiting | `10` | Defines the period over which rate limits are applied |

### Connection Management Configuration
| Parameter | Description | Default Value | Impact |
|-----------|-------------|---------------|---------|
| `HEARTBEAT_INTERVAL` | WebSocket heartbeat interval in seconds | `30` | Frequency of heartbeat messages to maintain connection |
| `RECONNECT_DELAY` | Delay between reconnection attempts in seconds | `5` | Time to wait before attempting to reconnect after disconnection |
| `MAX_RECONNECT_ATTEMPTS` | Maximum reconnection attempts | `10` | Number of times to retry connecting before giving up |

### Dry Run Configuration
| Parameter | Description | Default Value | Impact |
|-----------|-------------|---------------|---------|
| `DRY_RUN` | Enable dry run mode (true/false) | `false` | When true, simulates trades without executing on blockchain |
| `DRY_RUN_LOG_FILE` | Path to dry run log file | `dry_run_log.json` | File where simulated trades are logged for analysis |
| `STARTING_BALANCE` | Initial balance for simulation | `10000` | Starting balance used for PnL calculations in dry run mode |

## Dynamic Configuration Parameters (Database-Based)

These parameters can be adjusted during runtime through the database and affect trading behavior:

### Spread and Pricing Parameters
| Parameter | Description | Default Value | Impact |
|-----------|-------------|---------------|---------|
| `target_spread` | Target spread for market making in decimal (e.g., 0.0020 = 20 bps) | `0.0020` | Distance from mid-price at which orders are placed; affects profitability and competitiveness |

### Risk Management Parameters
| Parameter | Description | Default Value | Impact |
|-----------|-------------|---------------|---------|
| `max_exposure` | Maximum exposure per market in USD | `1000` | Limits total inventory exposure to protect capital |
| `kill_switch_threshold` | Loss threshold that triggers shutdown (decimal) | `0.10` | Percentage of starting balance loss that triggers immediate shutdown |
| `fat_finger_threshold` | Price deviation threshold (decimal) | `0.05` | Maximum allowable deviation from reference price to prevent erroneous orders |

### Order Sizing Parameters
| Parameter | Description | Default Value | Impact |
|-----------|-------------|---------------|---------|
| `min_order_size` | Minimum order size | `10` | Smallest allowed order size to meet minimum requirements |
| `max_order_size` | Maximum order size | `1000` | Largest allowed order size to manage risk exposure |

## Key Parameters Explained

### SPREAD_BPS (`target_spread`)
- **Description**: The target distance from mid-price at which the bot places its market-making orders. This is expressed in basis points (bps) as a decimal value (e.g., 0.0020 = 20 bps).
- **Default Value**: 0.0020 (20 bps)
- **Impact**: Affects profitability and competitiveness. Lower spreads increase competitiveness but reduce profit margins. Higher spreads offer better profit margins but may result in fewer fills.

### MAX_SKEW (`max_exposure`)
- **Description**: The maximum inventory imbalance allowed before the bot triggers aggressive hedging measures.
- **Default Value**: 1000 (USD)
- **Impact**: Controls risk exposure. Lower values trigger hedging sooner, reducing potential losses but increasing transaction costs. Higher values allow more inventory skew but increase risk exposure.

### MIN_PROFIT_TO_HEDGE
- **Note**: This parameter is not currently implemented in the configuration but could be added in future versions to determine the minimum USDC profit required to justify the gas cost of a CTF merge transaction.
- **Potential Impact**: Would help optimize hedging decisions by ensuring the cost of hedging transactions is justified by the profit potential.

## Configuration Best Practices

1. **Start Conservative**: Begin with default values and gradually adjust based on performance and risk tolerance.
2. **Monitor Risk**: Regularly check exposure levels and adjust `max_exposure` as needed.
3. **Spread Optimization**: Test different spread values to find the optimal balance between competitiveness and profitability.
4. **Environment Separation**: Use different configuration sets for development, testing, and production environments.
5. **Backup Configurations**: Regularly backup configuration values, especially when fine-tuning for optimal performance.