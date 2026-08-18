from engine.data import DataHandler
from engine.portfolio import Portfolio
from engine.execution import ExecutionEngine
from engine.backtest import BacktestEngine
from engine.metrics import PerformanceMetrics
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

# Create execution engine
execution_engine = ExecutionEngine(
    portfolio
)

# Create backtest engine
backtest = BacktestEngine(
    data=data,
    strategy=strategy,
    portfolio=portfolio,
    execution_engine=execution_engine,
    symbol="AAPL"
)

# Run backtest
result = backtest.run()

metrics = PerformanceMetrics(
  initial_capital=10000,
  portfolio_history=result["portfolio_history"],
  trade_history=result["trade_history"]
)

total_return = metrics.total_return()

print("\n===== QUANTFORGE BACKTEST =====")

print("Final Portfolio Value:", result["final_value"])
print("Cash:", result["cash"])
print("Position:", result["position"])
print("\n===== TRADE HISTORY =====")

for trade in result["trade_history"]:
    print(
        f"{trade['side']} | "
        f"Quantity: {trade['quantity']} | "
        f"Price: {trade['price']}"
    )

print("\n===== PORTFOLIO HISTORY =====")

for snapshot in result["portfolio_history"]:
    print(
        f"{snapshot['date'].date()} | "
        f"Portfolio Value: {snapshot['portfolio_value']}"
    )

print("\n===== PERFORMANCE =====")

print(
  f"Total Return: "
  f"{metrics.total_return():.2%}"
)

print(
  f"Annualized Return: "
  f"{metrics.annualized_return():.2%}"
)

print(
  f"Annualized Volatility: "
  f"{metrics.annualized_volatility():.2%}"
)

print(
  f"Sharpe Ratio: "
  f"{metrics.sharpe_ratio():.2f}"
)

print(
  f"Sortino Ratio: "
  f"{metrics.sortino_ratio():.2f}"
)

print(
  f"Maximum Drawdown: "
  f"{metrics.maximum_drawdown():.2%}"
)

print(
  f"Win Rate: "
  f"{metrics.win_rate():.2%}"
)

print(
  f"Average Win: "
  f"{metrics.average_win():.2f}"
)

print(
  f"Average Loss: "
  f"{metrics.average_loss():.2f}"
)

print(
  f"Profit Factor: "
  f"{metrics.profit_factor():.2f}"
)