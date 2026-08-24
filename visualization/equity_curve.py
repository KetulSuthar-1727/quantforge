import matplotlib.pyplot as plt


def plot_equity_curve(
  strategy_history,
  benchmark_history
):

  strategy_dates = [
    snapshot["date"]
    for snapshot in strategy_history
  ]

  strategy_values = [
    snapshot["portfolio_value"]
    for snapshot in strategy_history
  ]

  benchmark_dates = [
    snapshot["date"]
    for snapshot in benchmark_history
  ]

  benchmark_values = [
    snapshot["portfolio_value"]
    for snapshot in benchmark_history
  ]

  plt.figure(figsize=(12, 6))

  plt.plot(
    strategy_dates,
    strategy_values,
    label="QuantForge Strategy"
  )

  plt.plot(
    benchmark_dates,
    benchmark_values,
    label="Buy & Hold"
  )

  plt.title(
    "QuantForge Strategy vs Buy & Hold"
  )

  plt.xlabel("Date")
  plt.ylabel("Portfolio Value")

  plt.legend()

  plt.grid(True)

  plt.tight_layout()

  plt.show()