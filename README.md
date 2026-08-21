# Quant Forge

## Position Sizing Model

QuantForge uses a dynamic position-sizing model that adjusts exposure based on
signal confidence and market volatility.

### 1. Volatility Adjustment

The volatility adjustment compares current market volatility with the target
volatility:

Volatility Adjustment = Target Volatility / Current Volatility


### 2. Risk-Adjusted Allocation

The position allocation is calculated as:

Risk-Adjusted Allocation =
    Base Allocation
    × Signal Confidence
    × Volatility Adjustment


Substituting the volatility adjustment:

Risk-Adjusted Allocation =
    Base Allocation
    × Signal Confidence
    × (Target Volatility / Current Volatility)


The allocation is capped at the maximum allowed allocation:

Final Allocation =
    min(Risk-Adjusted Allocation, Maximum Allocation)


### 3. Capital Allocated

Capital allocated to the position:

Capital Allocated =
    Available Cash × Final Allocation


### 4. Position Quantity

The number of units/shares to trade:

Position Quantity =
    floor(Capital Allocated / Asset Price)


### Example

Assume:

- Available Cash = ₹10,000
- Base Allocation = 20%
- Maximum Allocation = 20%
- Signal Confidence = 0.80
- Target Volatility = 20%
- Current Volatility = 20%
- Asset Price = ₹100

Volatility Adjustment:

    20% / 20% = 1.0

Risk-Adjusted Allocation:

    20% × 0.80 × 1.0
    = 16%

Capital Allocated:

    ₹10,000 × 16%
    = ₹1,600

Position Quantity:

    floor(₹1,600 / ₹100)
    = 16 shares


### High-Volatility Example

If current volatility increases to 40%:

Volatility Adjustment:

    20% / 40%
    = 0.5

Risk-Adjusted Allocation:

    20% × 0.80 × 0.5
    = 8%

Capital Allocated:

    ₹10,000 × 8%
    = ₹800

Position Quantity:

    floor(₹800 / ₹100)
    = 8 shares

## Historical Volatility

Historical volatility tells us how much the price of an asset has moved
in the past.

We calculate it using the asset's historical closing prices.

### Step 1: Calculate Daily Return

First, we calculate how much the price changed from one day to the next.

Daily Return = (Today's Price - Yesterday's Price) / Yesterday's Price


### Step 2: Calculate Average Price Movement

We calculate the standard deviation of the daily returns.

This tells us how much the daily returns normally vary from their average.


### Step 3: Convert to Annual Volatility

Because our data is based on daily prices, we convert the daily volatility
into an approximate yearly volatility.

Annual Volatility = Daily Volatility × √252


We use 252 because the stock market has approximately 252 trading days
in a year.

### Example

If the calculated annual volatility is:

35.88%

it means that the asset has historically experienced relatively large
price movements, compared with an asset having a lower volatility.

QuantForge uses this volatility to adjust position size:

- Higher volatility → Smaller position
- Lower volatility → Larger position

This helps reduce risk when the market becomes more volatile.