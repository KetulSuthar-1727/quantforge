import math
import statistics

class VolatilityModel:

  def calculate_daily_returns(self, prices):
    returns = []

    for i in range(1, len(prices)):
      previous_price = prices[i - 1]
      current_price = prices[i]

      if previous_price <= 0:
        continue

      log_return = math.log(
        current_price / previous_price
      )

      returns.append(log_return)

    return returns

  def calculate(
    self,
    prices,
    window=20
  ):
    returns = self.calculate_daily_returns(
      prices
    )

    if len(returns) < 2:
      return 0

    recent_returns = returns[-window:]

    if len(recent_returns) < 2:
      return 0

    daily_volatility = statistics.stdev(
      recent_returns
    )

    annualized_volatility = (
      daily_volatility * math.sqrt(252)
    )

    return annualized_volatility