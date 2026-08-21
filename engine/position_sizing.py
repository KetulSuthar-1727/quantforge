class PositionSizer:

  def __init__(
    self,
    base_allocation=0.20,
    max_allocation=0.20,
    target_volatility=0.20
  ):
    self.base_allocation = base_allocation
    self.max_allocation = max_allocation
    self.target_volatility = target_volatility

  def calculate_allocation(
    self,
    signal_confidence,
    volatility
  ):
    if not 0 <= signal_confidence <= 1:
      raise ValueError(
        "Signal confidence must be between 0 and 1."
      )

    if volatility <= 0:
      raise ValueError(
        "Volatility must be greater than zero."
      )

    volatility_adjustment = (
      self.target_volatility / volatility
    )

    allocation = (
      self.base_allocation
      * signal_confidence
      * volatility_adjustment
    )

    allocation = min(
      allocation,
      self.max_allocation
    )

    return max(allocation, 0)

  def calculate_quantity(
    self,
    available_cash,
    price,
    signal_confidence,
    volatility
  ):
    if available_cash <= 0:
      return 0

    if price <= 0:
      raise ValueError(
        "Price must be greater than zero."
      )

    allocation = self.calculate_allocation(
      signal_confidence=signal_confidence,
      volatility=volatility
    )

    capital_to_use = (
      available_cash * allocation
    )

    quantity = int(
      capital_to_use / price
    )

    return quantity