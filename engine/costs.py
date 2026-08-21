class TransactionCostModel:

  def __init__(
    self,
    commission_rate=0.001,
    slippage_rate=0.0005
  ):
    self.commission_rate = commission_rate
    self.slippage_rate = slippage_rate

  def calculate(
    self,
    quantity,
    price
  ):
    trade_value = quantity * price

    return trade_value * self.commission_rate

  def execution_price(
    self,
    side,
    price
  ):
    if side == "BUY":
      return price * (
        1 + self.slippage_rate
      )

    if side == "SELL":
      return price * (
        1 - self.slippage_rate
      )

    raise ValueError(
      f"Invalid order side: {side}"
    )