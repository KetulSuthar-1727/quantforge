import streamlit as st
import pandas as pd
import numpy as np

from engine.data import DataHandler
from engine.portfolio import Portfolio
from engine.execution import ExecutionEngine
from engine.backtest import BacktestEngine
from engine.costs import TransactionCostModel
from engine.position_sizing import PositionSizer
from engine.volatility import VolatilityModel
from engine.benchmark import BuyAndHoldBenchmark
from strategies.moving_average import MovingAverageStrategy

st.set_page_config(
  page_title="QuantForge",
  page_icon="📈",
  layout="wide"
)

st.title("QuantForge")

st.caption(
  "Quantitative Trading Research & Backtesting Platform"
)

st.sidebar.header("Backtest Configuration")

initial_capital = st.sidebar.number_input(
  "Initial Capital",
  min_value=1000.0,
  value=10000.0,
  step=1000.0
)

fast_window = st.sidebar.number_input(
  "Fast Moving Average",
  min_value=1,
  value=3,
  step=1
)

slow_window = st.sidebar.number_input(
  "Slow Moving Average",
  min_value=2,
  value=5,
  step=1
)

run_backtest = st.sidebar.button(
  "Run Backtest"
)

if run_backtest:

  if fast_window >= slow_window:

    st.error(
      "Fast Moving Average must be smaller than "
      "Slow Moving Average."
    )

    st.stop()

  data_handler = DataHandler(
    "data/market_data.csv"
  )

  data = data_handler.load_data()

  strategy = MovingAverageStrategy(
    fast_window=fast_window,
    slow_window=slow_window
  )

  portfolio = Portfolio(
    initial_capital=initial_capital
  )

  cost_model = TransactionCostModel(
    commission_rate=0.001
  )

  execution_engine = ExecutionEngine(
    portfolio,
    cost_model
  )

  position_sizer = PositionSizer(
    base_allocation=0.20,
    max_allocation=0.20,
    target_volatility=0.20
  )

  volatility_model = VolatilityModel()

  backtest = BacktestEngine(
    data=data,
    strategy=strategy,
    portfolio=portfolio,
    execution_engine=execution_engine,
    position_sizer=position_sizer,
    volatility_model=volatility_model,
    symbol="AAPL"
  )

  result = backtest.run()

  benchmark = BuyAndHoldBenchmark(
    initial_capital=initial_capital
  )

  prices = data["Close"].tolist()

  dates = data.index.tolist()

  benchmark_result = benchmark.run(
    prices,
    dates
  )

  strategy_values = np.array([
    snapshot["portfolio_value"]
    for snapshot in result["portfolio_history"]
  ])

  running_max = np.maximum.accumulate(
    strategy_values
  )

  drawdown = (
    strategy_values - running_max
  ) / running_max

  final_value = result["final_value"]

  total_return = (
    (final_value - initial_capital)
    / initial_capital
  )

  max_drawdown = drawdown.min()

  benchmark_return = (
    benchmark_result["total_return"]
  )

  excess_return = (
    total_return - benchmark_return
  )

  st.success(
    "Backtest completed successfully."
  )

  st.subheader("Key Performance Metrics")

  col1, col2, col3, col4 = st.columns(4)

  col1.metric(
    "Final Value",
    f"{final_value:.2f}"
  )

  col2.metric(
    "Total Return",
    f"{total_return:.2%}"
  )

  col3.metric(
    "Max Drawdown",
    f"{max_drawdown:.2%}"
  )

  col4.metric(
    "Trades",
    len(result["trade_history"])
  )

  st.subheader(
    "Strategy vs Buy & Hold"
  )

  strategy_history = (
    result["portfolio_history"]
  )

  benchmark_history = (
    benchmark_result["portfolio_history"]
  )

  strategy_chart = pd.DataFrame(
    strategy_history
  )

  benchmark_chart = pd.DataFrame(
    benchmark_history
  )

  strategy_chart = (
    strategy_chart.set_index("date")
  )

  benchmark_chart = (
    benchmark_chart.set_index("date")
  )

  chart_data = pd.DataFrame({
    "QuantForge Strategy":
      strategy_chart["portfolio_value"],
    "Buy & Hold":
      benchmark_chart["portfolio_value"]
  })

  st.line_chart(
    chart_data,
    use_container_width=True
  )

  st.subheader("Drawdown")

  drawdown_chart = pd.DataFrame(
    {
      "Drawdown": drawdown
    },
    index=strategy_chart.index
  )

  st.line_chart(
    drawdown_chart,
    use_container_width=True
  )

  st.subheader(
    "Performance Comparison"
  )

  col1, col2, col3 = st.columns(3)

  col1.metric(
    "Strategy Return",
    f"{total_return:.2%}"
  )

  col2.metric(
    "Buy & Hold Return",
    f"{benchmark_return:.2%}"
  )

  col3.metric(
    "Excess Return",
    f"{excess_return:.2%}"
  )

  col1, col2 = st.columns(2)

  col1.metric(
    "Maximum Drawdown",
    f"{max_drawdown:.2%}"
  )

  col2.metric(
    "Number of Trades",
    len(result["trade_history"])
  )

  st.subheader("Trade History")

  if result["trade_history"]:

    trades = pd.DataFrame(
      result["trade_history"]
    )

    trades = trades.astype(str)

    st.dataframe(
      trades,
      use_container_width=True
    )

  else:

    st.info(
      "No trades were generated."
    )