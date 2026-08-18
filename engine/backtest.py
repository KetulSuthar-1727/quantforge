from engine.order import Order

class BacktestEngine:

  def __init__(
    self,
    data,
    strategy,
    portfolio,
    execution_engine,
    symbol
  ):
    self.data = data
    self.strategy = strategy
    self.portfolio = portfolio
    self.execution_engine = execution_engine
    self.symbol = symbol

  def run(self):
    result = self.strategy.generate_signal(self.data)
    portfolio_history = []
    for i, row in result.iterrows():

      signal = row["signal"]
      price = row["Close"]

      if (signal == "BUY"):
        order = Order(
            symbol=self.symbol,
            side="BUY",
            quantity=1,
            price=price
        )

        self.execution_engine.execute(order)

      elif signal == "SELL":

        if self.portfolio.position > 0:

          order = Order(
            symbol=self.symbol,
            side="SELL",
            quantity=self.portfolio.position,
            price=price
          )
          self.execution_engine.execute(order)

      portfolio_value = self.portfolio.get_value(price)
      portfolio_history.append({
        "date": row["Date"],
        "portfolio_value": portfolio_value
      })

    final_price = result.iloc[-1]["Close"]
    final_value = self.portfolio.get_value(final_price)
    return {
        "final_value": final_value,
        "cash": self.portfolio.cash,
        "position": self.portfolio.position,
        "trade_history": self.portfolio.trade_history,
        "portfolio_history": portfolio_history
    }