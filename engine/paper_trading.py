"""Fail-closed paper order workflow; deliberately separate from backtest fills."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
import logging
import re
import sqlite3
from typing import Optional, Protocol
from uuid import uuid4

logger = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc).isoformat()


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(str, Enum):
    PENDING = "pending_submission"
    SUBMITTED = "submitted"
    PARTIAL = "partially_filled"
    FILLED = "filled"
    REJECTED = "rejected"
    UNKNOWN = "unknown_reconciliation_required"
    CANCELLED = "cancelled"


_ALLOWED = {
    OrderStatus.PENDING: {OrderStatus.SUBMITTED, OrderStatus.REJECTED, OrderStatus.UNKNOWN},
    OrderStatus.SUBMITTED: {OrderStatus.PARTIAL, OrderStatus.FILLED, OrderStatus.REJECTED, OrderStatus.CANCELLED, OrderStatus.UNKNOWN},
    OrderStatus.PARTIAL: {OrderStatus.PARTIAL, OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.UNKNOWN},
    OrderStatus.UNKNOWN: {OrderStatus.SUBMITTED, OrderStatus.PARTIAL, OrderStatus.FILLED, OrderStatus.REJECTED, OrderStatus.CANCELLED, OrderStatus.UNKNOWN},
    OrderStatus.FILLED: {OrderStatus.FILLED},
    OrderStatus.REJECTED: {OrderStatus.REJECTED},
    OrderStatus.CANCELLED: {OrderStatus.CANCELLED},
}


@dataclass(frozen=True)
class OrderRequest:
    client_order_id: str
    symbol: str
    side: Side
    quantity: int
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[Decimal] = None
    strategy_id: str = ""
    signal_id: str = ""
    risk_decision_id: str = ""

    def __post_init__(self):
        if not isinstance(self.client_order_id, str) or not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", self.client_order_id):
            raise ValueError("Client order ID must be a nonempty stable identifier.")
        if not re.fullmatch(r"[A-Za-z0-9.-]{1,20}", self.symbol):
            raise ValueError("Malformed stock symbol.")
        object.__setattr__(self, "symbol", self.symbol.upper())
        if not isinstance(self.side, Side) or not isinstance(self.order_type, OrderType):
            raise ValueError("Unsupported side or order type.")
        if not isinstance(self.quantity, int) or isinstance(self.quantity, bool) or self.quantity <= 0:
            raise ValueError("Quantity must be a positive whole number.")
        if self.order_type == OrderType.LIMIT:
            price = _decimal(self.limit_price, "limit price")
            if price <= 0:
                raise ValueError("Limit price must be positive.")
            object.__setattr__(self, "limit_price", price)
        elif self.limit_price is not None:
            raise ValueError("Market orders cannot have a limit price.")

    @property
    def notional(self):
        return self.limit_price * self.quantity if self.limit_price is not None else None


def _decimal(value, label):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"Invalid {label}.") from None
    if not result.is_finite():
        raise ValueError(f"Invalid {label}.")
    return result


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reason: str
    decision_id: str = field(default_factory=lambda: str(uuid4()))
    evaluated_limits: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Account:
    paper: bool
    active: bool
    buying_power: Optional[Decimal]
    cash: Optional[Decimal] = None


@dataclass(frozen=True)
class RiskLimits:
    max_quantity: int
    max_order_notional: Decimal
    max_position_quantity: int
    max_open_orders: int
    allow_short: bool = False
    max_price_age_seconds: int = 60


@dataclass(frozen=True)
class Fill:
    fill_id: str
    quantity: int
    price: Decimal
    timestamp: str = field(default_factory=_now)


@dataclass(frozen=True)
class BrokerOrder:
    status: OrderStatus
    broker_order_id: Optional[str] = None
    fills: tuple = ()
    error: Optional[str] = None


class PaperBroker(Protocol):
    def verify_paper(self) -> bool: ...
    def get_account(self) -> Account: ...
    def submit_order(self, order: OrderRequest) -> BrokerOrder: ...
    def get_order_by_client_id(self, client_order_id: str) -> Optional[BrokerOrder]: ...


class OrderStore:
    """SQLite durable boundary; database errors always prevent submission."""
    def __init__(self, path):
        self.path = str(path)
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY, client_order_id TEXT UNIQUE NOT NULL,
                symbol TEXT NOT NULL, side TEXT NOT NULL, quantity INTEGER NOT NULL,
                order_type TEXT NOT NULL, limit_price TEXT, strategy_id TEXT,
                signal_id TEXT, risk_decision_id TEXT, status TEXT NOT NULL,
                broker_order_id TEXT, filled_quantity INTEGER NOT NULL DEFAULT 0,
                avg_fill_price TEXT, error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS fills (
                fill_id TEXT PRIMARY KEY, client_order_id TEXT NOT NULL,
                quantity INTEGER NOT NULL, price TEXT NOT NULL, timestamp TEXT NOT NULL,
                FOREIGN KEY(client_order_id) REFERENCES orders(client_order_id))""")

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def get(self, client_id):
        with self._connect() as db:
            row = db.execute("SELECT * FROM orders WHERE client_order_id=?", (client_id,)).fetchone()
        return row

    def open_count(self):
        with self._connect() as db:
            return db.execute("SELECT COUNT(*) FROM orders WHERE status IN (?, ?, ?, ?)",
                              (OrderStatus.PENDING.value, OrderStatus.SUBMITTED.value,
                               OrderStatus.PARTIAL.value, OrderStatus.UNKNOWN.value)).fetchone()[0]

    def exposure(self, symbol):
        with self._connect() as db:
            fills = db.execute("SELECT o.side, f.quantity FROM fills f JOIN orders o USING(client_order_id) WHERE o.symbol=?", (symbol,)).fetchall()
            rows = db.execute("SELECT side, quantity, filled_quantity FROM orders WHERE symbol=? AND status IN (?, ?, ?, ?)",
                              (symbol, OrderStatus.PENDING.value, OrderStatus.SUBMITTED.value,
                               OrderStatus.PARTIAL.value, OrderStatus.UNKNOWN.value)).fetchall()
        confirmed = sum((q if side == Side.BUY.value else -q) for side, q in fills)
        pending = sum((q - f if side == Side.BUY.value else -(q - f)) for side, q, f in rows)
        return confirmed + pending

    def create(self, request, risk_id):
        order_id, now = str(uuid4()), _now()
        with self._connect() as db:
            db.execute("INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, 0, NULL, NULL, ?, ?)",
                       (order_id, request.client_order_id, request.symbol, request.side.value,
                        request.quantity, request.order_type.value,
                        str(request.limit_price) if request.limit_price is not None else None,
                        request.strategy_id, request.signal_id, risk_id, OrderStatus.PENDING.value, now, now))
        return order_id

    def transition(self, client_id, broker_order):
        with self._connect() as db:
            row = db.execute("SELECT status, quantity, filled_quantity FROM orders WHERE client_order_id=?", (client_id,)).fetchone()
            if row is None:
                raise KeyError(client_id)
            old, quantity, prior_filled = OrderStatus(row[0]), row[1], row[2]
            new = broker_order.status
            if new not in _ALLOWED[old]:
                raise ValueError(f"Invalid order transition: {old.value} -> {new.value}.")
            seen = {r[0] for r in db.execute("SELECT fill_id FROM fills WHERE client_order_id=?", (client_id,))}
            fills = [f for f in broker_order.fills if f.fill_id not in seen]
            if any(f.quantity <= 0 or _decimal(f.price, "fill price") <= 0 for f in fills):
                raise ValueError("Broker returned an invalid fill.")
            total = prior_filled + sum(f.quantity for f in fills)
            if total > quantity or (new == OrderStatus.FILLED and total != quantity):
                raise ValueError("Broker fill quantities conflict with order quantity.")
            weighted = sum((_decimal(f.price, "fill price") * f.quantity for f in fills), Decimal(0))
            old_avg = Decimal(row[2] and (db.execute("SELECT avg_fill_price FROM orders WHERE client_order_id=?", (client_id,)).fetchone()[0] or "0") or "0")
            old_avg_value = old_avg * prior_filled
            avg = (old_avg_value + weighted) / total if total else None
            for fill in fills:
                db.execute("INSERT INTO fills VALUES (?, ?, ?, ?, ?)", (fill.fill_id, client_id, fill.quantity, str(_decimal(fill.price, "fill price")), fill.timestamp))
            # Broker supplied error strings can contain headers or other secrets.
            safe_error = ("broker reported rejection" if new == OrderStatus.REJECTED else
                          "broker status requires reconciliation" if new == OrderStatus.UNKNOWN else None)
            db.execute("UPDATE orders SET status=?, broker_order_id=COALESCE(?, broker_order_id), filled_quantity=?, avg_fill_price=?, error=?, updated_at=? WHERE client_order_id=?",
                       (new.value, broker_order.broker_order_id, total, str(avg) if avg is not None else None,
                        safe_error, _now(), client_id))

    def list_orders(self):
        with self._connect() as db:
            return db.execute("SELECT client_order_id, symbol, side, quantity, status, filled_quantity, avg_fill_price, error FROM orders ORDER BY created_at").fetchall()

    def positions(self):
        """Long/short net quantities derived only from durable broker fill events."""
        with self._connect() as db:
            rows = db.execute("SELECT o.symbol, o.side, f.quantity FROM fills f JOIN orders o USING(client_order_id)").fetchall()
        positions = {}
        for symbol, side, quantity in rows:
            positions[symbol] = positions.get(symbol, 0) + (quantity if side == Side.BUY.value else -quantity)
        return {symbol: quantity for symbol, quantity in positions.items() if quantity}


class RiskManager:
    def __init__(self, limits: RiskLimits, *, kill_switch):
        self.limits = limits
        self.kill_switch = bool(kill_switch)

    def assess(self, request, *, account, price, price_timestamp, store, now=None):
        checks = {"max_quantity": self.limits.max_quantity,
                  "max_order_notional": str(self.limits.max_order_notional),
                  "max_position_quantity": self.limits.max_position_quantity,
                  "max_open_orders": self.limits.max_open_orders}
        reason = "approved"
        current = now or datetime.now(timezone.utc)
        try:
            quoted = _decimal(price, "reference price")
            observed = datetime.fromisoformat(price_timestamp.replace("Z", "+00:00"))
            age = (current - observed).total_seconds()
        except (ValueError, AttributeError, TypeError):
            quoted, age = Decimal(0), float("inf")
        notional = quoted * request.quantity
        checks["evaluated_notional"] = str(notional)
        checks["price_age_seconds"] = age
        if self.kill_switch: reason = "kill switch is enabled"
        elif account is None or account.buying_power is None: reason = "account buying power is unavailable"
        elif not account.paper or not account.active: reason = "account is not verified active paper account"
        elif quoted <= 0 or age < 0 or age > self.limits.max_price_age_seconds: reason = "reference price is missing or stale"
        elif request.quantity > self.limits.max_quantity: reason = "maximum order quantity exceeded"
        elif notional > self.limits.max_order_notional: reason = "maximum order notional exceeded"
        elif store.open_count() >= self.limits.max_open_orders: reason = "maximum open orders exceeded"
        elif account.buying_power < notional: reason = "insufficient buying power"
        elif request.side == Side.SELL and not self.limits.allow_short and store.exposure(request.symbol) - request.quantity < 0:
            reason = "short selling is disabled or position is insufficient"
        elif abs(store.exposure(request.symbol) + (request.quantity if request.side == Side.BUY else -request.quantity)) > self.limits.max_position_quantity:
            reason = "maximum position quantity exceeded"
        if reason != "approved":
            logger.warning("risk_rejection", extra={"component": "risk", "symbol": request.symbol,
                                                    "reason": reason, "kill_switch": self.kill_switch})
        return RiskDecision(reason == "approved", reason, evaluated_limits=checks)


class OrderManager:
    def __init__(self, store: OrderStore, broker: PaperBroker, risk: RiskManager):
        self.store, self.broker, self.risk = store, broker, risk

    def submit(self, request, *, reference_price, price_timestamp):
        existing = self.store.get(request.client_order_id)
        if existing:
            expected_price = str(request.limit_price) if request.limit_price is not None else None
            if (existing[2] != request.symbol or existing[3] != request.side.value
                    or existing[4] != request.quantity or existing[5] != request.order_type.value
                    or existing[6] != expected_price or existing[7] != request.strategy_id
                    or existing[8] != request.signal_id):
                raise ValueError("Client order ID is already bound to a different request.")
            if OrderStatus(existing[10]) in {OrderStatus.PENDING, OrderStatus.UNKNOWN}:
                return self.reconcile(request.client_order_id)
            return existing
        if not self.broker.verify_paper():
            raise RuntimeError("Paper environment verification failed; submission refused.")
        account = self.broker.get_account()
        decision = self.risk.assess(request, account=account, price=reference_price,
                                    price_timestamp=price_timestamp, store=self.store)
        if not decision.approved:
            raise ValueError(f"Order rejected by risk: {decision.reason}")
        self.store.create(request, decision.decision_id)
        try:
            result = self.broker.submit_order(request)
        except (TimeoutError, ConnectionError, OSError):
            self.store.transition(request.client_order_id, BrokerOrder(OrderStatus.UNKNOWN, error="submission outcome requires reconciliation"))
            return self.store.get(request.client_order_id)
        self.store.transition(request.client_order_id, result)
        return self.store.get(request.client_order_id)

    def reconcile(self, client_order_id):
        row = self.store.get(client_order_id)
        if row is None: raise KeyError(client_order_id)
        remote = self.broker.get_order_by_client_id(client_order_id)
        if remote is None:
            self.store.transition(client_order_id, BrokerOrder(OrderStatus.UNKNOWN, error="broker has no matching order; no resubmission performed"))
        else:
            self.store.transition(client_order_id, remote)
        return self.store.get(client_order_id)


class FakePaperBroker:
    """Offline test broker: accepts orders but never invents fills."""
    def __init__(self, account=None, *, paper=True):
        self.account = account or Account(True, True, Decimal("100000"), Decimal("100000"))
        self.paper = paper
        self.orders = {}
        self.submissions = 0

    def verify_paper(self): return self.paper and self.account.paper
    def get_account(self): return self.account
    def submit_order(self, order):
        self.submissions += 1
        result = BrokerOrder(OrderStatus.SUBMITTED, f"fake-{order.client_order_id}")
        self.orders[order.client_order_id] = result
        return result
    def get_order_by_client_id(self, client_order_id): return self.orders.get(client_order_id)
