from engine.portfolio import Portfolio

def test_buy_updates_cash_and_position():
    portfolio = Portfolio(initial_capital=10000)

    portfolio.buy(
        quantity=5,
        price=100,
        transaction_cost=10
    )

    assert portfolio.cash == 9490
    assert portfolio.position == 5

def test_sell_records_correct_side():
    portfolio = Portfolio(initial_capital=10000)
    portfolio.buy(quantity=5, price=100)
    portfolio.sell(quantity=2, price=120)

    assert portfolio.position == 3
    assert portfolio.trade_history[-1]["side"] == "SELL"