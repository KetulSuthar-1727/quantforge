class Portfolio:
  def __init__(self, initial_capital):
    self.initial_capital = initial_capital
    self.cash = initial_capital
    self.position = 0
    self.trade_history = []

  def buy(self, quantity, price):
    cost = quantity * price

    if(cost > self.cash):
      raise ValueError("Insufficient cash to execute the buy order.")

    self.cash -= cost
    self.position += quantity

    self.trade_history.append({
      "side": "BUY",
      "quantity": quantity,
      "price": price
    })

  def sell(self, quantity, price):
    if(quantity > self.position):
      raise ValueError("Cannot sell more shares than currently owned.")

    revenue = quantity * price

    self.cash += revenue
    self.position -= quantity

    self.trade_history.append({
      "side": "BUY",
      "quantity": quantity,
      "price": price
    })

  def get_value(self, current_price):
    return self.cash + (self.position * current_price)

