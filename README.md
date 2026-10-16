# QuantForge

QuantForge is a local research project for testing historical trading strategies. It combines a Python bar-based backtesting engine with a standalone C++ order book and matching/execution engine exposed to Python through pybind11. It is for research and education; it does not connect to brokers or place live orders.

## Features

- Moving-average strategy with signal strength and volatility-aware position sizing.
- Historical OHLCV validation, portfolio accounting, commission, and slippage.
- Next-bar-open order execution with close-of-bar portfolio valuation.
- Buy-and-hold comparison on the same market dates and initial capital.
- Return, volatility, Sharpe, Sortino, drawdown, and FIFO realized trade statistics.
- Streamlit dashboard, CLI backtest, C++ engine, and deterministic Python/C++ tests.

## Position sizing and volatility adjustment

The implemented position sizer uses annualized volatility as a fraction (for example, `0.20` means 20%). For positive volatility, its allocation is:

```text
volatility adjustment = target volatility / current annualized volatility
allocation = min(base allocation × signal confidence × volatility adjustment,
                 maximum allocation)
allocation = max(allocation, 0)
quantity = int(available cash × allocation / sizing price)
```

The defaults in `PositionSizer` are a 20% base allocation, 20% maximum allocation, and 20% target volatility. Confidence must be between 0 and 1; volatility and sizing price must be positive (unless available cash is nonpositive, in which case quantity is zero). `int` truncates the positive share quantity to a whole unit. In the backtest, sizing uses the next bar's raw open; the execution model then adjusts that price for slippage and applies commission. The quantity calculation does not reserve either cost in advance.

`VolatilityModel` computes log returns from the supplied historical closes, takes sample standard deviation of up to the most recent 20 returns by default, and annualizes it with `sqrt(252)`. In the backtest, only closes through the preceding completed bar are supplied when sizing an order for the next bar's open. If fewer than two returns are available, volatility is zero and the backtest does not submit a buy.

For example, with 20% base and target volatility, 80% signal confidence, and 20% current annualized volatility, the allocation is `min(0.20 × 0.80 × 1, 0.20) = 16%`. With $10,000 available and a $100 sizing price, the calculated quantity is 16 shares. If volatility rises to 40%, the allocation becomes 8% and the quantity becomes 8 shares.

This formula describes the current implementation, not a guarantee of a fixed risk budget or loss limit. The max-allocation cap limits the fraction used by the sizing formula; it does not model gap risk, market impact, or transaction costs in advance.

## Repository layout

```text
engine/                 Python backtest, portfolio, data, costs, metrics
strategies/             Trading strategies
execution_engine/       C++ engine, pybind11 bindings, and CMake configuration
tests/                  Python and C++ tests
data/market_data.csv    Sample historical OHLCV input
app.py                  Streamlit dashboard
main.py                 CLI backtest
visualization/          Matplotlib equity-curve helper
```

## Requirements and setup

Python 3.8 or newer is supported by the source and dependency ranges. Install a C++17 compiler, CMake 3.16 or newer, and Python development headers. On Ubuntu, `build-essential` and `python3-dev` provide the compiler and headers.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The requirements include NumPy, pandas, Matplotlib, Streamlit, pybind11, and pytest. The CMake build requires the pybind11 CMake package provided by the Python installation above.

## Build the C++ engine and Python extension

```bash
cmake -S execution_engine -B build \
  -Dpybind11_DIR="$(python -m pybind11 --cmakedir)"
cmake --build build --parallel
```

The extension is emitted under `build/`. Include that directory on `PYTHONPATH` when running integration tests.

## Run a backtest

```bash
python main.py
streamlit run app.py
```

Both entry points read `data/market_data.csv`. The CSV must contain `Date`, `Open`, `High`, `Low`, `Close`, and `Volume`; dates must be unique, and OHLC prices must be positive and consistent. The dashboard lets you set the initial capital and moving-average windows.

Signals are calculated from completed bars. A signal from a completed bar is executed at the following bar's open, using only prices available by that decision time. The portfolio is marked at that bar's close, and a signal from the last bar is not executed without a later bar. The cost model applies slippage to execution price and commission to executed notional. The sample CLI configures both; the dashboard currently configures commission only.

The benchmark buys an integer number of shares at the first input close, retains unused cash, and values the position at each input close. It uses no transaction costs and assumes buy-and-hold from the first observation. The strategy and benchmark histories use the source market dates.

## Metrics conventions and limits

- Total return compares the final marked portfolio value with initial capital.
- Annualized return compounds over elapsed calendar time between the first and last portfolio snapshots (365.25 days per year).
- Daily returns are successive snapshot returns; annualized volatility and Sharpe use sample standard deviation and 252 periods per year.
- The annual risk-free decimal rate is converted to a daily effective rate. Sortino downside deviation includes every observation relative to that daily threshold.
- Maximum drawdown is a nonpositive fraction, so `-0.20` means a 20% peak-to-trough decline.
- Realized trade P&L uses FIFO matching of recorded long buys and sells and includes proportional entry and exit commissions. Unmatched open shares are omitted. Slippage is already reflected in recorded execution prices, so it is not subtracted a second time.
- A zero denominator produces a ratio of zero; profit factor is infinite when there are gains and no losses. The dashboard labels this case explicitly.

Portfolio return includes mark-to-market gains and costs in portfolio cash/value. Trade P&L is realized P&L for matched quantities and is a separate statistic. These historical results do not model market impact, taxes, corporate actions, short selling, or operational constraints.

## Tests

Run Python tests (including the C++ binding integration tests after building the extension):

```bash
PYTHONPATH=build pytest
```

Run the C++ suite:

```bash
(cd build && ctest --output-on-failure)
```

For Python-only unit tests without a built extension:

```bash
pytest tests/test_backtest.py tests/test_data.py tests/test_portfolio.py tests/test_metrics.py
```

All tests use local deterministic inputs; no live data service, broker account, or API credential is required.

## Development and future work

GitHub Actions builds the C++ library and Python extension, runs CTest, and runs Python tests including the extension integration tests. Local commands above match the CI sequence.

Live market-data infrastructure, broker integration, paper trading, production trading-risk controls, and deployment readiness are future work and are not implemented here.
