# QuantForge

QuantForge is a local research project for testing historical trading strategies. It combines a Python bar-based backtesting engine with a standalone C++ order book and matching/execution engine exposed to Python through pybind11. It is for research and education; it does not connect to brokers or place live orders.

## Features

- Moving-average strategy with signal strength and volatility-aware position sizing.
- Historical OHLCV validation, portfolio accounting, commission, and slippage.
- Next-bar-open order execution with close-of-bar portfolio valuation.
- Buy-and-hold comparison on the same market dates and initial capital.
- Return, volatility, Sharpe, Sortino, drawdown, and FIFO realized trade statistics.
- Read-only US stock market-data retrieval through the Alpaca Market Data API.
- Market-data validation, pagination, bounded retries, and sanitized provider errors.
- Streamlit dashboard with historical backtesting and a separate market-data explorer.
- Standalone C++ order-book and matching/execution engine exposed to Python through pybind11.
- Deterministic Python and C++ tests.

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
engine/market_data/     Market-data interface, Alpaca provider, validation, errors
strategies/             Trading strategies
execution_engine/       C++ engine, pybind11 bindings, and CMake configuration
tests/                  Python and C++ tests
data/market_data.csv    Sample historical OHLCV input
app.py                  Streamlit dashboard
main.py                 CLI backtest
visualization/          Matplotlib equity-curve helper
build/                  Generated CMake build and Python extension (local)
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

## Read-only US market data

QuantForge includes an Alpaca market-data provider for retrieving US stock OHLCV bars. The Streamlit dashboard exposes this functionality in a separate **US Market Data Explorer**. It is independent of the CSV-based historical backtest workflow.

### Configure Alpaca credentials

Create an Alpaca account and obtain market-data API credentials from the provider. Add the following variables to a local `.env` file in the repository root:

```dotenv
ALPACA_API_KEY=your_api_key
ALPACA_SECRET_KEY=your_secret_key
```

Replace the placeholder values locally. Never commit `.env`, paste credentials into source code, or include credentials in logs or screenshots. The repository's `.gitignore` should exclude `.env`.

Install the project's dependencies using the requirements file:

```bash
python -m pip install -r requirements.txt
```

The dashboard loads `.env` when the market-data request is submitted. The historical CSV backtest does not require Alpaca credentials.

### Use the market-data explorer

Start the dashboard:

```bash
streamlit run app.py
```

Open **US Market Data Explorer**, expand **Fetch intraday market data**, enter a US stock symbol, select an interval, and click **Fetch market data**.

Supported intervals are:

| Interval | Meaning |
|---|---|
| `1Min` | One-minute bars |
| `5Min` | Five-minute bars |
| `15Min` | Fifteen-minute bars |
| `1Hour` | One-hour bars |
| `1Day` | Daily bars |

The explorer displays the retrieved bars, a close-price chart, the latest bar timestamp in UTC, and a conservative freshness warning.

### Data validation and limitations

The provider normalizes returned data into the canonical columns `Date`, `Open`, `High`, `Low`, `Close`, and `Volume`. Validation checks required columns, timestamps, numeric and finite values, positive prices, nonnegative volume, OHLC consistency, and duplicate timestamps. Results are sorted chronologically.

Requests support pagination and bounded retries for transient network failures and selected retryable HTTP responses. Authentication and other permanent failures are reported as sanitized errors.

The default feed is `iex`. Available feed settings depend on Alpaca account access and provider support. IEX data must not be treated as consolidated coverage of every US trading venue. Data availability, permissions, market hours, holidays, and feed coverage can affect the latest timestamp. The dashboard's freshness warning is a heuristic, not a market-calendar-aware guarantee.

This integration retrieves market-data bars; it does not implement a live streaming feed, submit orders, connect a trading strategy to a broker, or execute live trades. Retrieved bars are not automatically passed into the CSV-based backtester.

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

**Implemented:** historical CSV-based backtesting, the C++ order book and matching/execution engine, and read-only Alpaca US stock OHLCV retrieval through the dashboard.

**Future work:**
- Live market-data streaming and freshness monitoring.
- Additional provider abstraction and data-source coverage.
- Integration of external market data into backtesting through an explicit, tested workflow.
- Broker integration and paper trading.
- Expanded risk controls, operational monitoring, and deployment readiness.
- Live-trading readiness only after separate testing, risk validation, and explicit broker integration.

QuantForge is a research and educational project. Market-data retrieval does not establish that a strategy is profitable or safe to trade, and the project does not currently submit broker orders or execute live trades.