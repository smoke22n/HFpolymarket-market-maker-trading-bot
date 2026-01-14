# Backtesting Engine Details

## Overview

The backtesting engine simulates trading performance using historical market data to evaluate strategy effectiveness before deploying to live markets. The engine replicates real-world trading conditions including latency, slippage, and fill probability.

## Latency Simulation

### Network Latency Modeling

The backtesting engine accounts for realistic network delays between seeing market data and executing orders:

```
Effective Quote Time = Market Data Receipt Time + Simulated Latency
```

Where simulated latency is randomly sampled from a distribution based on real-world measurements:
- Mean latency: 75ms
- Standard deviation: 15ms
- Distribution: Normal distribution truncated at 50-100ms range

### Processing Delay

Additional computational delay is added to simulate:
- Strategy computation time
- Risk validation checks
- Order preparation overhead

Typical processing delay: 5-10ms

### Total Round-Trip Latency

The total delay from market event to order placement is modeled as:

```
Total Latency = Network Latency + Processing Delay + Random Variation
```

## Fill Probability Simulation

### Conservative Fill Model

The conservative model assumes an order is filled only if the market price moves *through* the order price:

- **Condition**: A buy order at price P is filled only if market price drops below P
- **Advantage**: More realistic for low-latency strategies
- **Disadvantage**: May underestimate fill rates

### Optimistic Fill Model

The optimistic model assumes an order is filled if the market price merely *touches* the order price:

- **Condition**: A buy order at price P is filled if market price reaches P
- **Advantage**: Higher fill probability estimates
- **Disadvantage**: May overestimate actual fills

### Adaptive Fill Model

The backtesting engine uses an adaptive model that considers:

1. **Order Size vs. Available Liquidity**: Larger orders have lower fill probability
2. **Market Volatility**: Higher volatility increases fill probability
3. **Time in Queue**: Orders remaining in queue longer have higher fill probability

## Slippage Modeling

### Slippage Calculation

Slippage is modeled based on order size relative to available liquidity:

```
Slippage = Base Slippage + (Order Size / Available Liquidity) × Liquidity Impact Factor
```

### Slippage Tiers

Different slippage models apply based on order characteristics:

#### Small Orders (< 1% of available depth)
- Slippage: 0.1-0.3%
- Assumption: Minimal market impact

#### Medium Orders (1-5% of available depth)
- Slippage: 0.3-0.8%
- Assumption: Moderate market impact

#### Large Orders (> 5% of available depth)
- Slippage: 0.8-2.0%+
- Assumption: Significant market impact

### Dynamic Slippage

Slippage varies based on market conditions:

```
Actual Slippage = Base Slippage × (1 + Market Stress Factor)
```

Where Market Stress Factor increases during high volatility periods.

## Execution Simulation

### Order Matching Algorithm

The backtesting engine uses a time-sequenced matching algorithm:

1. **Sort Events**: All market data updates and simulated orders are sorted chronologically
2. **Apply Latency**: Adjust order placement times based on simulated latency
3. **Check Conditions**: Determine if orders would have been filled at each market update
4. **Execute Trades**: Record fills with appropriate slippage applied
5. **Update Positions**: Adjust inventory and risk metrics

### Partial Fill Handling

Large orders are split into smaller chunks to simulate partial fills:

```
Fill Ratio = min(1.0, Available Volume at Price Level / Order Quantity)
```

Remaining unfilled portions are carried forward to subsequent price levels.

## Performance Metrics

### PnL Calculation

The backtesting engine calculates multiple PnL measures:

#### Realized PnL
- Calculated from actual filled trades
- Includes transaction fees and slippage costs

#### Unrealized PnL
- Based on current market prices for open positions
- Uses bid-ask midpoint as fair value

#### Total PnL
- Sum of realized and unrealized PnL
- Accounts for all trading costs

### Risk-Adjusted Metrics

#### Sharpe Ratio
```
Sharpe Ratio = (Mean Return - Risk-Free Rate) / Standard Deviation of Returns
```

#### Maximum Drawdown
- Peak-to-trough decline in account value
- Measures worst-case scenario

#### Win Rate
- Percentage of profitable trades
- Indicates strategy reliability

## Validation Methods

### Out-of-Sample Testing

- Reserve 20% of historical data for validation
- Train strategy on 80% of data
- Validate performance on held-out data

### Walk-Forward Analysis

- Split data into consecutive windows
- Optimize parameters on early windows
- Test on subsequent windows
- Prevents overfitting to historical data

### Sensitivity Analysis

- Vary key parameters to assess robustness
- Test performance under different market conditions
- Identify parameter ranges that maintain profitability