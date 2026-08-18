import math


class PerformanceMetrics:

  def __init__(
    self,
    initial_capital,
    portfolio_history,
    trade_history
  ):
    self.initial_capital = initial_capital
    self.portfolio_history = portfolio_history
    self.trade_history = trade_history

  def portfolio_values(self):
    return [
      snapshot["portfolio_value"]
      for snapshot in self.portfolio_history
    ]

  def total_return(self):
    values = self.portfolio_values()

    if not values:
      return 0

    final_value = values[-1]

    return (
      (final_value - self.initial_capital)
      / self.initial_capital
    )

  def daily_returns(self):
    values = self.portfolio_values()

    returns = []

    for i in range(1, len(values)):
      previous_value = values[i - 1]
      current_value = values[i]

      if previous_value == 0:
        returns.append(0)
      else:
        returns.append(
          (current_value - previous_value)
          / previous_value
        )

    return returns

  def annualized_return(self):
    if not self.portfolio_history:
      return 0

    initial_value = self.initial_capital
    final_value = self.portfolio_values()[-1]

    if initial_value <= 0 or final_value <= 0:
      return 0

    start_date = self.portfolio_history[0]["date"]
    end_date = self.portfolio_history[-1]["date"]

    days = (end_date - start_date).days

    if days <= 0:
      return self.total_return()

    years = days / 365.25

    return (
      (final_value / initial_value)
      ** (1 / years)
    ) - 1

  def annualized_volatility(self):
    returns = self.daily_returns()

    if len(returns) < 2:
      return 0

    mean_return = sum(returns) / len(returns)

    variance = sum(
      (r - mean_return) ** 2
      for r in returns
    ) / (len(returns) - 1)

    daily_volatility = math.sqrt(variance)

    return daily_volatility * math.sqrt(252)

  def sharpe_ratio(self, risk_free_rate=0):
    returns = self.daily_returns()

    if len(returns) < 2:
      return 0

    mean_return = sum(returns) / len(returns)

    variance = sum(
      (r - mean_return) ** 2
      for r in returns
    ) / (len(returns) - 1)

    daily_volatility = math.sqrt(variance)

    if daily_volatility == 0:
      return 0

    daily_risk_free_rate = (
      risk_free_rate / 252
    )

    excess_returns = [
      r - daily_risk_free_rate
      for r in returns
    ]

    mean_excess_return = (
      sum(excess_returns)
      / len(excess_returns)
    )

    return (
      mean_excess_return
      / daily_volatility
    ) * math.sqrt(252)

  def sortino_ratio(self, risk_free_rate=0):
    returns = self.daily_returns()

    if len(returns) < 2:
      return 0

    daily_risk_free_rate = (
      risk_free_rate / 252
    )

    excess_returns = [
      r - daily_risk_free_rate
      for r in returns
    ]

    negative_returns = [
      r
      for r in excess_returns
      if r < 0
    ]

    if not negative_returns:
      return 0

    downside_variance = sum(
      r ** 2
      for r in negative_returns
    ) / len(negative_returns)

    downside_deviation = math.sqrt(
      downside_variance
    )

    if downside_deviation == 0:
      return 0

    mean_excess_return = (
      sum(excess_returns)
      / len(excess_returns)
    )

    return (
      mean_excess_return
      / downside_deviation
    ) * math.sqrt(252)

  def maximum_drawdown(self):
    values = self.portfolio_values()

    if not values:
      return 0

    peak = values[0]
    max_drawdown = 0

    for value in values:
      if value > peak:
        peak = value

      drawdown = (
        (value - peak)
        / peak
      )

      if drawdown < max_drawdown:
        max_drawdown = drawdown

    return max_drawdown

  def trade_pnl(self):
    trades = self.trade_history

    pnl = []
    buy_price = None

    for trade in trades:

      if trade["side"] == "BUY":
        buy_price = trade["price"]

      elif (
        trade["side"] == "SELL"
        and buy_price is not None
      ):
        profit = (
          trade["price"]
          - buy_price
        ) * trade["quantity"]

        pnl.append(profit)

        buy_price = None

    return pnl

  def win_rate(self):
    pnl = self.trade_pnl()

    if not pnl:
      return 0

    winning_trades = [
      value
      for value in pnl
      if value > 0
    ]

    return (
      len(winning_trades)
      / len(pnl)
    )

  def average_win(self):
    pnl = self.trade_pnl()

    winning_trades = [
      value
      for value in pnl
      if value > 0
    ]

    if not winning_trades:
      return 0

    return (
      sum(winning_trades)
      / len(winning_trades)
    )

  def average_loss(self):
    pnl = self.trade_pnl()

    losing_trades = [
      value
      for value in pnl
      if value < 0
    ]

    if not losing_trades:
      return 0

    return (
      sum(losing_trades)
      / len(losing_trades)
    )

  def profit_factor(self):
    pnl = self.trade_pnl()

    gross_profit = sum(
      value
      for value in pnl
      if value > 0
    )

    gross_loss = abs(
      sum(
        value
        for value in pnl
        if value < 0
      )
    )

    if gross_loss == 0:
      return 0

    return gross_profit / gross_loss