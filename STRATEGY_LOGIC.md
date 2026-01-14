# Strategy Logic

## Overview

The trading bot employs a sophisticated market-making strategy that dynamically adjusts quotes based on market conditions, inventory levels, and risk parameters. The core logic balances profitability with risk management through mathematical models and real-time adjustments.

## Fair Value Calculation

The fair value represents the bot's estimate of the true market price, calculated using order book depth information.

### Mid-Price Formula

The primary fair value calculation uses the weighted mid-price formula:

```
Fair Value = (Best Bid Price × Ask Volume + Best Ask Price × Bid Volume) / (Best Bid Volume + Best Ask Volume)
```

Where:
- Best Bid Price: Highest price someone is willing to pay
- Best Ask Price: Lowest price someone is willing to sell
- Best Bid Volume: Volume available at the best bid
- Best Ask Volume: Volume available at the best ask

### Alternative Fair Value Models

#### Simple Mid-Point
```
Fair Value = (Best Bid Price + Best Ask Price) / 2
```

#### Depth-Weighted Average
For more sophisticated fair value estimation using multiple levels of the order book:

```
Fair Value = Σ(Price_i × Volume_i) / Σ(Volume_i)
```

Where the sum includes the top N levels of the order book.

## Inventory Skew Logic

The bot adjusts its quotes based on current inventory position to manage risk exposure.

### Linear Skew Adjustment

The skew adjustment shifts the fair value based on inventory levels:

```
Adjusted Fair Value = Fair Value - (Skew Factor × Current Position)
```

Where:
- Current Position: Net position in tokens (positive for long, negative for short)
- Skew Factor: Sensitivity parameter controlling how much to adjust based on position

### Exponential Skew Adjustment

For more aggressive risk management with larger positions:

```
Adjusted Fair Value = Fair Value - (Skew Factor × tanh(Current Position / Scale Factor))
```

This provides gentler adjustments for small positions and more aggressive adjustments for large positions.

### Example Scenario

If the bot is long 100 YES tokens and the skew factor is 0.005:
- Original Fair Value: 0.6500
- Adjustment: -0.005 × 100 = -0.50
- Adjusted Fair Value: 0.6450

This shifts quotes downward to encourage selling YES tokens and reduce the long position.

## Spread Calculation

The bid-ask spread determines the profit margin and is adjusted based on market conditions:

### Base Spread Formula

```
Base Spread = Min Spread + (Market Volatility × Volatility Multiplier)
```

### Dynamic Spread Adjustment

Spreads widen during periods of high volatility or low liquidity:

```
Effective Spread = Base Spread × (1 + Market Stress Factor)
```

## CTF Hedging Mechanism

The bot uses the Gnosis Conditional Tokens Framework for hedging positions across correlated markets.

### Hedge Decision Logic

The bot decides to hedge based on:

1. **Threshold-Based**: When position exceeds predetermined risk limits
2. **Time-Based**: Periodic rebalancing at regular intervals
3. **Opportunity-Based**: When profitable hedging opportunities arise

### Conditional Token Mechanics

When hedging across correlated outcomes:

1. **Position Assessment**: Evaluate current exposure across all related markets
2. **Hedge Calculation**: Determine optimal hedge ratio to minimize overall risk
3. **Execution Timing**: Execute hedges when spreads are favorable
4. **Merge Operations**: Combine conditional tokens when conditions are met

### Hedge Execution Conditions

The bot executes hedges when:

- Net exposure exceeds position limits
- Arbitrage opportunities exist between related markets
- Correlation coefficients indicate profitable hedge scenarios
- Market conditions favor the hedge execution

## Risk Management Parameters

### Position Limits
- Maximum position size per market
- Maximum aggregate position across all markets
- Maximum daily loss threshold

### Pricing Constraints
- Minimum spread width
- Maximum price deviation from fair value
- Price velocity limits to prevent erratic quoting