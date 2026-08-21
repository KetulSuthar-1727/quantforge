class Portfolio:
  def __init__(self, initial_capital):
    self.initial_capital = initial_capital
    self.cash = initial_capital
    self.position = 0
    self.trade_history = []

  def buy(self, quantity, price, transaction_cost=0):
    cost = quantity * price
    total_cost = cost + transaction_cost

    if(total_cost > self.cash):
      raise ValueError("Insufficient cash to execute the buy order.")

    self.cash -= total_cost
    self.position += quantity

    self.trade_history.append({
      "side": "BUY",
      "quantity": quantity,
      "price": price,
      "transaction_cost": transaction_cost
    })

  def sell(self, quantity, price, transaction_cost=0):
    if(quantity > self.position):
      raise ValueError("Cannot sell more shares than currently owned.")

    revenue = quantity * price
    net_revenue = revenue - transaction_cost

    self.cash += net_revenue
    self.position -= quantity

    self.trade_history.append({
      "side": "BUY",
      "quantity": quantity,
      "price": price,
      "transaction_cost": transaction_cost
    })

  def get_value(self, current_price):
    return self.cash + (self.position * current_price)

