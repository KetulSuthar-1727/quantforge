class ExecutionEngine:

  def __init__(self, portfolio, cost_model):
    self.portfolio = portfolio
    self.cost_model = cost_model

  def execute(self, order):

    execution_price = self.cost_model.execution_price(
      side=order.side,
      price=order.price
    )

    transaction_cost = self.cost_model.calculate(
      quantity=order.quantity,
      price=execution_price
    )

    if order.side == "BUY":

      self.portfolio.buy(
        quantity=order.quantity,
        price=execution_price,
        transaction_cost=transaction_cost
      )

    elif order.side == "SELL":

      self.portfolio.sell(
        quantity=order.quantity,
        price=execution_price,
        transaction_cost=transaction_cost
      )

    else:
      raise ValueError(
        f"Invalid order side: {order.side}"
      )