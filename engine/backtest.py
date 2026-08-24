from engine.order import Order
from engine.volatility import VolatilityModel

class BacktestEngine:

  def __init__(
    self,
    data,
    strategy,
    portfolio,
    execution_engine,
    position_sizer,
    volatility_model,
    symbol
  ):
    self.data = data
    self.strategy = strategy
    self.portfolio = portfolio
    self.execution_engine = execution_engine
    self.position_sizer = position_sizer
    self.volatility_model=volatility_model
    self.symbol = symbol

  def run(self):

    result = self.strategy.generate_signal(
      self.data
    )

    portfolio_history = []

    for i, row in result.iterrows():

      signal = row["signal"]
      price = row["Close"]

      if signal == "BUY":

        confidence = row["signal_strength"]

        historical_prices = (
          result.loc[
            :row.name,
            "Close"
          ].tolist()
        )

        volatility = self.volatility_model.calculate(
          prices=historical_prices,
          window=20
        )

        if volatility > 0:

          quantity = self.position_sizer.calculate_quantity(
            available_cash=self.portfolio.cash,
            price=price,
            signal_confidence=confidence,
            volatility=volatility
          )

        else:
          quantity = 0

        if quantity > 0:

          order = Order(
            symbol=self.symbol,
            side="BUY",
            quantity=quantity,
            price=price
          )

          self.execution_engine.execute(
            order
          )

      elif signal == "SELL":

        if self.portfolio.position > 0:

          order = Order(
            symbol=self.symbol,
            side="SELL",
            quantity=self.portfolio.position,
            price=price
          )

          self.execution_engine.execute(
            order
          )

      portfolio_value = (
        self.portfolio.get_value(price)
      )

      portfolio_history.append({
        "date": row["Date"],
        "portfolio_value": portfolio_value
      })

    final_price = result.iloc[-1]["Close"]

    final_value = (
      self.portfolio.get_value(final_price)
    )

    return {
      "final_value": final_value,
      "cash": self.portfolio.cash,
      "position": self.portfolio.position,
      "trade_history": self.portfolio.trade_history,
      "portfolio_history": portfolio_history
    }