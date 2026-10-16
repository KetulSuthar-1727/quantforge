import quantforge_cpp as qf

def test_cpp_engine_matches_orders_from_python():
    order_book = qf.OrderBook()
    engine = qf.ExecutionEngine(order_book)

    buy_order = qf.Order(
        1, "AAPL", qf.OrderSide.BUY, 101.0, 10
    )
    sell_order = qf.Order(
        2, "AAPL", qf.OrderSide.SELL, 100.0, 6
    )

    assert engine.submit_order(buy_order) == qf.OrderStatus.ACCEPTED
    assert engine.submit_order(sell_order) == qf.OrderStatus.ACCEPTED

    trades = engine.get_trade_history()

    assert len(trades) == 1
    assert trades[0].symbol == "AAPL"
    assert trades[0].quantity == 6
    assert trades[0].price == 100.0


def test_cpp_engine_rejects_duplicate_order_ids():
    order_book = qf.OrderBook()
    engine = qf.ExecutionEngine(order_book)

    first_order = qf.Order(
        1, "AAPL", qf.OrderSide.BUY, 101.0, 10
    )
    duplicate_order = qf.Order(
        1, "AAPL", qf.OrderSide.SELL, 100.0, 5
    )

    assert engine.submit_order(first_order) == qf.OrderStatus.ACCEPTED
    assert engine.submit_order(duplicate_order) == qf.OrderStatus.REJECTED

    assert engine.get_trade_history() == []


def test_cpp_engine_rejects_different_symbols():
    order_book = qf.OrderBook()
    engine = qf.ExecutionEngine(order_book)

    buy_order = qf.Order(
        1, "AAPL", qf.OrderSide.BUY, 101.0, 10
    )
    sell_order = qf.Order(
        2, "MSFT", qf.OrderSide.SELL, 100.0, 5
    )

    assert engine.submit_order(buy_order) == qf.OrderStatus.ACCEPTED
    assert engine.submit_order(sell_order) == qf.OrderStatus.REJECTED

    assert engine.get_trade_history() == []
