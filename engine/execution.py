class ExecutionEngine:

    def __init__(self, portfolio):
        self.portfolio = portfolio

    def execute(self, order):
        if order.side == "BUY":
            self.portfolio.buy(
                quantity=order.quantity,
                price=order.price
            )

        elif order.side == "SELL":
            self.portfolio.sell(
                quantity=order.quantity,
                price=order.price
            )

        else:
            raise ValueError(f"Invalid order side: {order.side}")