from datetime import datetime, timezone
from decimal import Decimal

import pytest

from engine.paper_trading import (
    Account, BrokerOrder, FakePaperBroker, Fill, OrderManager, OrderRequest,
    OrderStatus, OrderStore, OrderType, RiskLimits, RiskManager, Side,
)


def setup(tmp_path):
    store = OrderStore(tmp_path / "paper.sqlite")
    broker = FakePaperBroker()
    risk = RiskManager(RiskLimits(100, Decimal("20000"), 200, 5), kill_switch=False)
    return store, broker, OrderManager(store, broker, risk)


def request(cid="c-1", quantity=10):
    return OrderRequest(cid, "aapl", Side.BUY, quantity, strategy_id="moving_average", signal_id="s-1")


def submit(manager, order=None):
    return manager.submit(order or request(), reference_price="100",
                          price_timestamp=datetime.now(timezone.utc).isoformat())


def test_validation_and_decimal_limit_price():
    with pytest.raises(ValueError): OrderRequest("x", "AAPL", Side.BUY, 0)
    with pytest.raises(ValueError): OrderRequest("x", "../AAPL", Side.BUY, 1)
    order = OrderRequest("x", "aapl", Side.BUY, 2, OrderType.LIMIT, Decimal("10.25"))
    assert order.symbol == "AAPL" and order.notional == Decimal("20.50")


def test_idempotent_submission_and_risk_never_calls_broker(tmp_path):
    store, broker, manager = setup(tmp_path)
    first = submit(manager)
    second = submit(manager)
    assert first[0] == second[0]
    assert broker.submissions == 1
    assert OrderStatus(second[10]) == OrderStatus.SUBMITTED
    with pytest.raises(ValueError, match="different request"):
        submit(manager, request("c-1", quantity=9))

    rejected = OrderManager(store, broker, RiskManager(
        RiskLimits(1, Decimal("50"), 200, 5), kill_switch=False))
    with pytest.raises(ValueError, match="maximum order quantity"):
        submit(rejected, request("c-2"))
    assert broker.submissions == 1


def test_live_account_and_kill_switch_fail_closed(tmp_path):
    store = OrderStore(tmp_path / "orders.sqlite")
    broker = FakePaperBroker(Account(False, True, Decimal("100000")), paper=False)
    manager = OrderManager(store, broker, RiskManager(RiskLimits(100, Decimal("20000"), 200, 5), kill_switch=False))
    with pytest.raises(RuntimeError, match="verification"):
        submit(manager)
    assert broker.submissions == 0

    broker = FakePaperBroker()
    manager = OrderManager(store, broker, RiskManager(RiskLimits(100, Decimal("20000"), 200, 5), kill_switch=True))
    with pytest.raises(ValueError, match="kill switch"):
        submit(manager)
    assert broker.submissions == 0


def test_stale_price_and_missing_buying_power_rejected(tmp_path):
    store, broker, manager = setup(tmp_path)
    with pytest.raises(ValueError, match="stale"):
        manager.submit(request(), reference_price=100, price_timestamp="2020-01-01T00:00:00+00:00")
    broker.account = Account(True, True, None)
    with pytest.raises(ValueError, match="buying power"):
        submit(manager, request("c-2"))
    assert broker.submissions == 0


def test_ambiguous_submission_reconciles_without_resubmission(tmp_path):
    store, broker, manager = setup(tmp_path)
    def timeout(_): raise TimeoutError()
    broker.submit_order = timeout
    row = submit(manager)
    assert OrderStatus(row[10]) == OrderStatus.UNKNOWN
    assert broker.submissions == 0
    again = submit(manager)
    assert OrderStatus(again[10]) == OrderStatus.UNKNOWN
    assert broker.submissions == 0


def test_partial_fill_deduplicates_and_positions_use_confirmed_fills(tmp_path):
    store, broker, manager = setup(tmp_path)
    submit(manager)
    partial = BrokerOrder(OrderStatus.PARTIAL, "fake-c-1", (Fill("f1", 4, Decimal("101")),))
    store.transition("c-1", partial)
    store.transition("c-1", partial)
    row = store.get("c-1")
    assert row[12] == 4 and Decimal(row[13]) == Decimal("101")
    assert store.positions() == {"AAPL": 4}
    with pytest.raises(ValueError, match="Invalid order transition"):
        store.transition("c-1", BrokerOrder(OrderStatus.PENDING))


def test_fill_average_price_accumulates(tmp_path):
    store, broker, manager = setup(tmp_path)
    submit(manager)
    store.transition("c-1", BrokerOrder(OrderStatus.PARTIAL, fills=(Fill("f1", 4, Decimal("100")),)))
    store.transition("c-1", BrokerOrder(OrderStatus.FILLED, fills=(Fill("f2", 6, Decimal("110")),)))
    row = store.get("c-1")
    assert row[12] == 10 and Decimal(row[13]) == Decimal("106")
    assert OrderStatus(row[10]) == OrderStatus.FILLED


def test_no_broker_order_after_restart_does_not_resubmit(tmp_path):
    store, broker, manager = setup(tmp_path)
    manager.submit(request(), reference_price=100, price_timestamp=datetime.now(timezone.utc).isoformat())
    broker.submit_order = lambda _: (_ for _ in ()).throw(AssertionError("must not resubmit"))
    # Existing submitted records are returned as-is until explicit reconciliation.
    assert OrderStatus(submit(manager)[10]) == OrderStatus.SUBMITTED
