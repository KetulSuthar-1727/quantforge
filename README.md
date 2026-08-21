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

Daily log return:

r_t = ln(P_t / P_(t-1))

Annualized Volatility:

σ_annual = StdDev(r_t) × √252

Where:
- P_t = current closing price
- P_(t-1) = previous closing price
- 252 = approximate number of trading days per year