"""Streamlit interface for local historical QuantForge backtests."""

import pandas as pd
import streamlit as st

from engine.backtest import BacktestEngine
from engine.benchmark import BuyAndHoldBenchmark, has_sufficient_benchmark_history
from engine.costs import TransactionCostModel
from engine.data import DataHandler
from engine.execution import ExecutionEngine
from engine.metrics import PerformanceMetrics
from engine.portfolio import Portfolio
from engine.position_sizing import PositionSizer
from engine.volatility import VolatilityModel
from strategies.moving_average import MovingAverageStrategy


st.set_page_config(page_title="QuantForge", page_icon="📈", layout="wide")
st.title("QuantForge")
st.caption("Historical strategy research and backtesting")

st.sidebar.header("Backtest configuration")
initial_capital = st.sidebar.number_input("Initial capital", min_value=1000.0, value=10000.0, step=1000.0)
fast_window = st.sidebar.number_input("Fast moving average", min_value=1, value=3, step=1)
slow_window = st.sidebar.number_input("Slow moving average", min_value=2, value=5, step=1)

if st.sidebar.button("Run backtest"):
    if fast_window >= slow_window:
        st.error("Fast moving average must be smaller than slow moving average.")
        st.stop()

    try:
        data = DataHandler("data/market_data.csv").load_data()
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
        symbol="AAPL",
    )
    result = engine.run()
    metrics = PerformanceMetrics(initial_capital, result["portfolio_history"], result["trade_history"])
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
    st.subheader("Portfolio performance")
    columns = st.columns(4)
    columns[0].metric("Initial capital", f"${initial_capital:,.2f}")
    columns[1].metric("Final value", f"${result['final_value']:,.2f}")
    columns[2].metric("Total return", f"{metrics.total_return():.2%}")
    columns[3].metric("Annualized return", f"{metrics.annualized_return():.2%}")
    columns = st.columns(4)
    columns[0].metric("Annualized volatility", f"{metrics.annualized_volatility():.2%}")
    columns[1].metric("Sharpe ratio", f"{metrics.sharpe_ratio():.2f}")
    columns[2].metric("Sortino ratio", f"{metrics.sortino_ratio():.2f}")
    columns[3].metric("Maximum drawdown", f"{metrics.maximum_drawdown():.2%}")

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

    pnl = metrics.trade_pnl()
    profit_factor = metrics.profit_factor()
    columns = st.columns(5)
    columns[0].metric("Closed FIFO matches", str(len(pnl)))
    columns[1].metric("Win rate", f"{metrics.win_rate():.1%}")
    columns[2].metric("Average win", f"${metrics.average_win():,.2f}")
    columns[3].metric("Average loss", f"${metrics.average_loss():,.2f}")
    columns[4].metric("Profit factor", "∞ (no losses)" if profit_factor == float("inf") else f"{profit_factor:.2f}")

    st.subheader("Execution history")
    if result["trade_history"]:
        st.dataframe(pd.DataFrame(result["trade_history"]), hide_index=True, use_container_width=True)
    else:
        st.info("The strategy did not execute any trades for this configuration.")
