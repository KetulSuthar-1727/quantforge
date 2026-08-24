class BuyAndHoldBenchmark:

  def __init__(
    self,
    initial_capital
  ):
    self.initial_capital = initial_capital

  def run(
    self,
    prices,
    dates
  ):

    if len(prices) < 2:
      raise ValueError(
        "At least two prices are required."
      )

    if len(prices) != len(dates):
      raise ValueError(
        "Prices and dates must have the same length."
      )

    initial_price = prices[0]

    quantity = int(
      self.initial_capital / initial_price
    )

    remaining_cash = (
      self.initial_capital
      - (quantity * initial_price)
    )

    portfolio_history = []

    for i in range(len(prices)):

      portfolio_value = (
        quantity * prices[i]
        + remaining_cash
      )

      portfolio_history.append({
        "date": dates[i],
        "portfolio_value": portfolio_value
      })

    final_value = portfolio_history[-1][
      "portfolio_value"
    ]

    total_return = (
      (final_value - self.initial_capital)
      / self.initial_capital
    )

    return {
      "initial_capital": self.initial_capital,
      "quantity": quantity,
      "initial_price": initial_price,
      "final_price": prices[-1],
      "final_value": final_value,
      "total_return": total_return,
      "portfolio_history": portfolio_history
    }