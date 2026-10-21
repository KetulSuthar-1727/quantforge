"""Streamlit interface for local historical QuantForge backtests."""

import pandas as pd
import streamlit as st
import logging
import os

from dotenv import load_dotenv
from engine.market_data import AlpacaMarketDataProvider, MarketDataError
from engine.monitoring import METRICS, configure_logging, health_report
from engine.backtest import BacktestEngine
from engine.benchmark import BuyAndHoldBenchmark, has_sufficient_benchmark_history
from engine.costs import TransactionCostModel
from engine.data import DataHandler
from engine.dataset import create_dataset, fetch_alpaca_dataset, load_csv_dataset
from engine.execution import ExecutionEngine
from engine.metrics import PerformanceMetrics
from engine.portfolio import Portfolio
from engine.scanner import StockScanner
from engine.strategy import available_strategies, get_strategy
from engine.position_sizing import PositionSizer
from engine.volatility import VolatilityModel
from strategies.moving_average import MovingAverageStrategy
from strategies.mean_reversion import MeanReversionStrategy


st.set_page_config(page_title="QuantForge", page_icon="📈", layout="wide")
configure_logging()
logger = logging.getLogger(__name__)
if not st.session_state.get("quantforge_started"):
    logger.info("application_started", extra={"component": "runtime"})
    st.session_state["quantforge_started"] = True
st.title("QuantForge")
st.caption("Historical strategy research and backtesting")

st.header("Historical multi-stock scanner")
strategy_options = {cls.name: cls for cls in available_strategies()}
scan_strategy_name = st.selectbox("Scan strategy", list(strategy_options), key="scan_strategy")
scan_class = strategy_options[scan_strategy_name]
scan_symbols_text = st.text_input("Symbols (comma separated)", "AAPL, MSFT, NVDA", key="scan_symbols")
scan_timeframe = st.selectbox("Scan timeframe", ["1Min", "5Min", "15Min", "1Hour", "1Day"], index=4, key="scan_timeframe")
if scan_class.strategy_id == "moving_average":
    scan_fast = st.number_input("Scan fast window", min_value=1, value=3, key="scan_fast")
    scan_slow = st.number_input("Scan slow window", min_value=2, value=5, key="scan_slow")
    scan_parameters = {"fast_window": int(scan_fast), "slow_window": int(scan_slow)}
else:
    scan_window = st.number_input("Scan window", min_value=2, value=20, key="scan_window")
    scan_zscore = st.number_input("Entry z-score", min_value=0.1, value=2.0, key="scan_zscore")
    scan_parameters = {"window": int(scan_window), "entry_zscore": float(scan_zscore)}
scan_signature = (scan_class.strategy_id, tuple(sorted(scan_parameters.items())), scan_symbols_text, scan_timeframe)
if st.button("Run historical scan", key="run_historical_scan"):
    try:
        selected_strategy = get_strategy(scan_class.strategy_id, **scan_parameters)
        symbols = [part.strip() for part in scan_symbols_text.split(",")]
        load_dotenv(".env")
        provider = AlpacaMarketDataProvider()
        scan = StockScanner(symbols, selected_strategy,
                            lambda symbol: fetch_alpaca_dataset(provider, symbol=symbol, interval=scan_timeframe),
                            timeframe=scan_timeframe).scan()
        st.session_state["scan_result"] = scan.to_dict()
        st.session_state["scan_signature"] = scan_signature
    except (ValueError, MarketDataError) as exc:
        st.error(f"Could not run scan: {exc}")
stored_scan = st.session_state.get("scan_result")
if stored_scan is not None:
    if st.session_state.get("scan_signature") == scan_signature:
        st.caption(f"{scan_strategy_name} parameters: {scan_parameters}. Signals are strategy opinions only; no risk approval or orders are created.")
        st.json(stored_scan["summary"])
        st.dataframe(pd.DataFrame(stored_scan["results"]), hide_index=True, use_container_width=True)
    else:
        st.info("Scan controls changed. Run the scan again to view results for this configuration.")

st.header("Monitoring and diagnostics")
health = health_report(provider_configured=bool(os.getenv("ALPACA_API_KEY") and os.getenv("ALPACA_SECRET_KEY")))
st.metric("Application status", health["status"].upper())
monitor_columns = st.columns(3)
monitor_columns[0].metric("Market data", health["checks"]["market_data"]["state"].upper())
monitor_columns[1].metric("Scheduler", health["checks"]["scheduler"]["state"].upper())
monitor_columns[2].metric("Broker", "UNAVAILABLE")
with st.expander("Component health details"):
    st.json({name: {"state": item["state"], "detail": item["detail"]}
             for name, item in health["checks"].items()})
scan_metrics = health["metrics"]["scans"]
data_metrics = health["metrics"]["market_data"]
st.caption(f"Scans: {scan_metrics['total']} total, {scan_metrics['successful']} successful, "
           f"{scan_metrics['failed']} failed; consecutive failures: {scan_metrics['consecutive_failures']}. "
           f"Last outcome: {scan_metrics['last_outcome'] or 'none'}; "
           f"last successful scan: {scan_metrics['last_successful_scan_at'] or 'none'}.")
if data_metrics["last_outcome"]:
    freshness = (f"{data_metrics['latest_age_seconds']:.0f}s old" if data_metrics["latest_age_seconds"] is not None
                 else "age unavailable")
    st.caption(f"Market-data fetch: {data_metrics['last_outcome']} for {data_metrics['last_symbol']}; "
               f"latest bar {data_metrics['latest_timestamp']} ({freshness}); "
               f"{data_metrics['fetches']} fetches, {data_metrics['failures']} failures.")
else:
    st.caption("Market-data fetch: no outcome recorded in this process. Provider credentials alone do not establish health.")
if health["metrics"]["safety_block_reason"]:
    st.warning(f"Safety block: {health['metrics']['safety_block_reason']}")
if scan_metrics["recent_errors"]:
    with st.expander("Recent scan errors"):
        st.dataframe(pd.DataFrame(scan_metrics["recent_errors"]), hide_index=True, use_container_width=True)
st.caption("Metrics reset when the Python process restarts. Scheduler run history is persisted only when a SchedulerStore is configured. Broker connectivity and order submission are unavailable.")

st.header("US Market Data Explorer")
st.caption(
    "Read-only US stock market data from Alpaca. "
    "The selected feed may not represent the entire US market."
)

with st.expander("Fetch intraday market data", expanded=False):
    symbol = st.text_input("US stock symbol", value="AAPL", key="explorer_symbol").strip().upper()
    interval = st.selectbox(
        "Bar interval",
        options=["1Min", "5Min", "15Min", "1Hour", "1Day"],
        index=1,
    )

    if st.button("Fetch market data"):
        if not symbol:
            st.error("Enter a valid stock symbol.")
        else:
            try:
                load_dotenv(".env")
                provider = AlpacaMarketDataProvider()
                bars = provider.fetch_bars(
                    symbol=symbol,
                    interval=interval,
                )


                latest_bar = bars["Date"].max()
                now_utc = pd.Timestamp.now(tz="UTC")
                age = now_utc - latest_bar

                st.success(f"Received {len(bars)} bars for {symbol}.")

                st.metric(
                    "Latest bar (UTC)",
                    latest_bar.strftime("%Y-%m-%d %H:%M:%S UTC"),
                )

                # This is a conservative warning, not a definitive market-hours check.
                stale_thresholds = {
                    "1Min": pd.Timedelta(minutes=15),
                    "5Min": pd.Timedelta(minutes=30),
                    "15Min": pd.Timedelta(minutes=60),
                    "1Hour": pd.Timedelta(hours=3),
                    "1Day": pd.Timedelta(days=4),
                }

                if age > stale_thresholds[interval]:
                    st.warning(
                        "The newest bar is older than the expected freshness threshold. "
                        "This may be normal outside market hours, on holidays, or when "
                        "the selected feed has limited coverage. Check the timestamp "
                        "before relying on this data."
                    )
                else:
                    st.caption(
                        f"Newest bar is approximately {age} old. "
                        "Feed coverage and market hours can affect freshness."
                    )

                st.line_chart(
                    bars.set_index("Date")[["Close"]],
                    use_container_width=True,
                )
                st.dataframe(
                    bars.tail(100),
                    hide_index=True,
                    use_container_width=True,
                )
            except MarketDataError as exc:
                st.error(f"Market data request failed: {exc}")
            except (ValueError, OSError) as exc:
                st.error(f"Could not fetch market data: {exc}")

st.sidebar.header("Backtest configuration")
data_source = st.sidebar.selectbox("Historical data source", ["CSV file", "Alpaca historical bars"])
if data_source == "CSV file":
    csv_path = st.sidebar.text_input("CSV path", value="data/market_data.csv")
    data_symbol = st.sidebar.text_input("Dataset symbol", value="AAPL").strip().upper()
    data_interval = st.sidebar.selectbox("CSV bar timeframe", ["1Min", "5Min", "15Min", "1Hour", "1Day"], index=4)
    start_text = end_text = ""
else:
    data_symbol = st.sidebar.text_input("US stock symbol", value="AAPL", key="backtest_symbol").strip().upper()
    data_interval = st.sidebar.selectbox("Backtest bar interval", ["1Min", "5Min", "15Min", "1Hour", "1Day"], index=4)
    start_text = st.sidebar.text_input("Start timestamp (optional, UTC/ISO-8601)", value="")
    end_text = st.sidebar.text_input("End timestamp (optional, UTC/ISO-8601)", value="")
    csv_path = None

source_signature = (data_source, csv_path, data_symbol, data_interval, start_text.strip(), end_text.strip())
if st.sidebar.button("Load selected dataset"):
    try:
        if data_source == "CSV file":
            selected_dataset = load_csv_dataset(csv_path, symbol=data_symbol)
        else:
            load_dotenv(".env")
            provider = AlpacaMarketDataProvider()
            selected_dataset = fetch_alpaca_dataset(
                provider, symbol=data_symbol, interval=data_interval,
                start=start_text.strip() or None, end=end_text.strip() or None,
            )
        st.session_state["backtest_dataset"] = selected_dataset
        st.session_state["backtest_dataset_signature"] = source_signature
        st.success(f"Loaded {selected_dataset.provenance.bar_count} bars ({selected_dataset.provenance.fingerprint[:12]}…).")
    except (MarketDataError, ValueError, OSError) as exc:
        st.error(f"Could not load selected dataset: {exc}")

selected_dataset = st.session_state.get("backtest_dataset")
if selected_dataset is not None and st.session_state.get("backtest_dataset_signature") == source_signature:
    with st.expander("Selected dataset diagnostics", expanded=False):
        st.json(selected_dataset.provenance.to_dict())
        st.dataframe(selected_dataset.data.head(20), hide_index=True, use_container_width=True)

initial_capital = st.sidebar.number_input("Initial capital", min_value=1000.0, value=10000.0, step=1000.0)
fast_window = st.sidebar.number_input("Fast moving average", min_value=1, value=3, step=1)
slow_window = st.sidebar.number_input("Slow moving average", min_value=2, value=5, step=1)

if st.sidebar.button("Run backtest"):
    if fast_window >= slow_window:
        st.error("Fast moving average must be smaller than slow moving average.")
        st.stop()

    try:
        # CSV stays a one-click, explicit backtest path. Alpaca data must be
        # fetched with the separate Load action and match the current controls.
        if data_source == "CSV file":
            if st.session_state.get("backtest_dataset_signature") == source_signature:
                selected_dataset = st.session_state.get("backtest_dataset")
            else:
                selected_dataset = create_dataset(
                    DataHandler(csv_path).load_data(), source="csv", symbol=data_symbol,
                    timeframe=data_interval, source_reference=csv_path,
                )
        elif st.session_state.get("backtest_dataset_signature") == source_signature:
            selected_dataset = st.session_state.get("backtest_dataset")
            if selected_dataset is None:
                raise ValueError("Load the selected Alpaca dataset before running the backtest.")
        else:
            raise ValueError("Dataset controls changed. Load the selected dataset before running the backtest.")
        data = selected_dataset.data
    except (OSError, ValueError) as exc:
        st.error(f"Could not load market data: {exc}")
        st.stop()
    if data.empty:
        st.error("The market data file contains no observations to backtest.")
        st.stop()

    portfolio = Portfolio(initial_capital=initial_capital)
    engine = BacktestEngine(
        data=data,
        strategy=MovingAverageStrategy(fast_window=fast_window, slow_window=slow_window),
        portfolio=portfolio,
        execution_engine=ExecutionEngine(portfolio, TransactionCostModel(commission_rate=0.001)),
        position_sizer=PositionSizer(base_allocation=0.20, max_allocation=0.20, target_volatility=0.20),
        volatility_model=VolatilityModel(),
        symbol=data_symbol,
    )
    result = engine.run_with_metadata(dataset_provenance=selected_dataset.provenance)
    metrics = PerformanceMetrics(
        initial_capital, result["portfolio_history"], result["trade_history"],
        timeframe=selected_dataset.provenance.timeframe,
    )
    prices = data["Close"].tolist()
    benchmark = None
    if has_sufficient_benchmark_history(prices):
        benchmark = BuyAndHoldBenchmark(initial_capital).run(prices, data["Date"].tolist())

    strategy = pd.DataFrame(result["portfolio_history"])
    strategy["date"] = pd.to_datetime(strategy["date"], errors="coerce")
    strategy = strategy.dropna(subset=["date"]).sort_values("date").drop_duplicates("date", keep="last")
    strategy = strategy.rename(columns={"portfolio_value": "Strategy"})
    strategy = strategy[["date", "Strategy"]]
    if benchmark is not None:
        benchmark_frame = pd.DataFrame(benchmark["portfolio_history"])
        benchmark_frame["date"] = pd.to_datetime(benchmark_frame["date"], errors="coerce")
        benchmark_frame = benchmark_frame.dropna(subset=["date"]).sort_values("date").drop_duplicates("date", keep="last")
        benchmark_frame = benchmark_frame.rename(columns={"portfolio_value": "Buy & hold"})
        chart = strategy.merge(benchmark_frame[["date", "Buy & hold"]], on="date", how="outer")
    else:
        chart = strategy
    chart = chart.sort_values("date").set_index("date")

    st.success("Backtest completed.")
    with st.expander("Run provenance and configuration", expanded=False):
        st.json(result["run_metadata"])
    st.subheader("Portfolio performance")
    columns = st.columns(4)
    columns[0].metric("Initial capital", f"${initial_capital:,.2f}")
    columns[1].metric("Final value", f"${result['final_value']:,.2f}")
    columns[2].metric("Total return", f"{metrics.total_return():.2%}" if metrics.total_return() is not None else "Unavailable")
    columns[3].metric("Annualized return", f"{metrics.annualized_return():.2%}" if metrics.annualized_return() is not None else "Unavailable")
    columns = st.columns(4)
    columns[0].metric("Annualized volatility", f"{metrics.annualized_volatility():.2%}" if metrics.annualized_volatility() is not None else "Unavailable")
    columns[1].metric("Sharpe ratio", f"{metrics.sharpe_ratio():.2f}" if metrics.sharpe_ratio() is not None else "Unavailable")
    columns[2].metric("Sortino ratio", f"{metrics.sortino_ratio():.2f}" if metrics.sortino_ratio() is not None else "Unavailable")
    columns[3].metric("Maximum drawdown", f"{metrics.maximum_drawdown():.2%}" if metrics.maximum_drawdown() is not None else "Unavailable")

    st.subheader("Strategy vs buy and hold")
    if benchmark is None:
        st.info("At least two valid market observations are required for a buy-and-hold comparison. Showing the available strategy history only.")
    if chart.empty:
        st.info("No dated portfolio observations are available to chart.")
    else:
        st.line_chart(chart, use_container_width=True)
        if benchmark is not None:
            comparison = pd.DataFrame({
                "Portfolio": ["Strategy", "Buy & hold"],
                "Final value": [result["final_value"], benchmark["final_value"]],
                "Total return": [metrics.total_return(), benchmark["total_return"]],
            })
            st.dataframe(comparison, hide_index=True, use_container_width=True)

    st.subheader("Strategy drawdown")
    drawdowns = pd.DataFrame({"Drawdown": metrics.drawdowns()}, index=pd.to_datetime([item["date"] for item in result["portfolio_history"]]))
    st.line_chart(drawdowns, use_container_width=True)
    duration = metrics.drawdown_duration()
    if duration is not None:
        st.caption(f"Maximum drawdown duration: {duration['max_observations']} observations ({duration['max_days']:.0f} days); current underwater duration: {duration['current_observations']} observations ({duration['current_days']:.0f} days).")
    cumulative = metrics.cumulative_returns()
    if cumulative is not None:
        st.subheader("Cumulative return")
        st.line_chart(pd.DataFrame({"Cumulative return": cumulative}, index=pd.to_datetime([item["date"] for item in result["portfolio_history"]])), use_container_width=True)

    pnl = metrics.trade_pnl()
    profit_factor = metrics.profit_factor()
    columns = st.columns(5)
    columns[0].metric("Closed FIFO matches", str(len(pnl)))
    columns[1].metric("Win rate", f"{metrics.win_rate():.1%}" if metrics.win_rate() is not None else "Unavailable")
    columns[2].metric("Average win", f"${metrics.average_win():,.2f}" if metrics.average_win() is not None else "Unavailable")
    columns[3].metric("Average loss", f"${metrics.average_loss():,.2f}" if metrics.average_loss() is not None else "Unavailable")
    columns[4].metric("Profit factor", "Unavailable" if profit_factor is None else ("∞ (no losses)" if profit_factor == float("inf") else f"{profit_factor:.2f}"))
    st.caption(f"Recorded trades: {metrics.trade_count()}; recorded transaction costs/fees: ${metrics.transaction_costs():,.2f}; slippage cost: unavailable (reference prices are not stored); turnover: {metrics.turnover():.2f}x" if metrics.turnover() is not None else f"Recorded trades: {metrics.trade_count()}; recorded transaction costs/fees: ${metrics.transaction_costs():,.2f}; slippage cost and turnover: unavailable.")
    st.caption("Exposure is unavailable because this backtest records portfolio values but not per-bar positions. Results are historical backtests; they do not establish profitability, remove lookahead or survivorship bias, or represent broker-confirmed paper trading.")

    st.subheader("Execution history")
    if result["trade_history"]:
        st.dataframe(pd.DataFrame(result["trade_history"]), hide_index=True, use_container_width=True)
    else:
        st.info("The strategy did not execute any trades for this configuration.")
