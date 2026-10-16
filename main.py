from engine.data import DataHandler
from engine.portfolio import Portfolio
from engine.execution import ExecutionEngine
from engine.backtest import BacktestEngine
from engine.metrics import PerformanceMetrics
from engine.costs import TransactionCostModel
from engine.position_sizing import PositionSizer
from engine.volatility import VolatilityModel
from engine.benchmark import BuyAndHoldBenchmark
from visualization.equity_curve import plot_equity_curve
from strategies.moving_average import MovingAverageStrategy

# Load market data
data_handler = DataHandler("data/market_data.csv")
data = data_handler.load_data()

# Create strategy
strategy = MovingAverageStrategy(
    fast_window=3,
    slow_window=5
)

# Create portfolio
portfolio = Portfolio(
    initial_capital=10000
)

# Calulating cost
cost_model = TransactionCostModel(
  commission_rate=0.001,
  slippage_rate=0.0005
)

# Volatility model
volatility_model = VolatilityModel()

# Create execution engine
execution_engine = ExecutionEngine(
    portfolio,
    cost_model
)

position_sizer = PositionSizer(
  base_allocation=0.20,
  max_allocation=0.20,
  target_volatility=0.20
)

# Create backtest engine
backtest = BacktestEngine(
    data=data,
    strategy=strategy,
    portfolio=portfolio,
    execution_engine=execution_engine,
    position_sizer=position_sizer,
    volatility_model=volatility_model,
    symbol="AAPL"
)

# Run backtest
result = backtest.run()

# Benchmark results
benchmark = BuyAndHoldBenchmark(
  initial_capital=10000
)

prices = data["Close"].tolist()
dates = data["Date"].tolist()

benchmark_result = benchmark.run(
  prices,
  dates
)

metrics = PerformanceMetrics(
  initial_capital=10000,
  portfolio_history=result["portfolio_history"],
  trade_history=result["trade_history"]
)

total_return = metrics.total_return()

plot_equity_curve(
  strategy_history=result["portfolio_history"],
  benchmark_history=benchmark_result["portfolio_history"]
)

print("\n===== QUANTFORGE BACKTEST =====")

print("Final Portfolio Value:", result["final_value"])
print("Total Return:", f"{metrics.total_return():.2%}")
print("Annualized Return:", f"{metrics.annualized_return():.2%}")
print("Annualized Volatility:", f"{metrics.annualized_volatility():.2%}")
print("Sharpe Ratio:", f"{metrics.sharpe_ratio():.3f}")
print("Sortino Ratio:", f"{metrics.sortino_ratio():.3f}")
print("Maximum Drawdown:", f"{metrics.maximum_drawdown():.2%}")
print("Closed FIFO Matches:", len(metrics.trade_pnl()))
print("Win Rate:", f"{metrics.win_rate():.2%}")
profit_factor = metrics.profit_factor()
print("Profit Factor:", "infinite (no losses)" if profit_factor == float("inf") else f"{profit_factor:.3f}")
print("Cash:", result["cash"])
print("Position:", result["position"])
print("\n===== TRADE HISTORY =====")

for trade in result["trade_history"]:
    print(
        f"{trade['side']} | "
        f"Quantity: {trade['quantity']} | "
        f"Price: {trade['price']:.4f} | "
        f"Transaction cost: {trade['transaction_cost']:.4f}"
    )

print("\n===== PORTFOLIO HISTORY =====")

for snapshot in result["portfolio_history"]:
    print(
        f"{snapshot['date'].date()} | "
        f"Portfolio Value: {snapshot['portfolio_value']}"
    )

print("\n===== BUY & HOLD BENCHMARK =====")

print(
  "Final Value:",
  benchmark_result["final_value"]
)

print(
  "Total Return:",
  f"{benchmark_result['total_return']:.2%}"
)
print("Strategy excess return:", f"{metrics.total_return() - benchmark_result['total_return']:.2%}")
