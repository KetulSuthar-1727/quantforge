"""Small strategy contract, signal schema, and built-in strategy registry."""
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from enum import Enum


class SignalType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass(frozen=True)
class StrategySignal:
    signal_type: SignalType
    reason: str
    signal_timestamp: object
    data_timestamp: object
    confidence: float = 0.0

    def to_dict(self):
        result = asdict(self)
        result["signal_type"] = self.signal_type.value
        for key in ("signal_timestamp", "data_timestamp"):
            value = result[key]
            result[key] = value.isoformat() if hasattr(value, "isoformat") else value
        return result


class Strategy(ABC):
    strategy_id = "abstract"
    version = "1.0"
    name = "Strategy"
    description = ""
    default_parameters = {}

    def __init__(self, **parameters):
        unknown = set(parameters) - set(self.default_parameters)
        if unknown:
            raise ValueError(f"Unknown strategy parameter(s): {', '.join(sorted(unknown))}.")
        self.parameters = {**self.default_parameters, **parameters}
        self.validate_parameters(self.parameters)

    @classmethod
    def validate_parameters(cls, parameters):
        if set(parameters) != set(cls.default_parameters):
            raise ValueError("Strategy parameters do not match the declared schema.")

    @property
    def required_lookback(self):
        return 1

    @abstractmethod
    def generate_signal(self, data):
        """Return the legacy-compatible frame with signal/signal_strength columns."""

    def evaluate(self, data):
        result = self.generate_signal(data)
        row = result.iloc[-1]
        signal_type = SignalType(row["signal"])
        timestamp = row["Date"]
        return StrategySignal(signal_type, f"{self.name}: {signal_type.value.lower()} evaluation",
                              timestamp, timestamp, float(row.get("signal_strength", 0.0)))


_STRATEGIES = {}


def register_strategy(strategy_class):
    if not isinstance(strategy_class, type) or not issubclass(strategy_class, Strategy):
        raise TypeError("Registered strategies must subclass Strategy.")
    key = strategy_class.strategy_id
    if not key or key == "abstract" or key in _STRATEGIES:
        raise ValueError(f"Invalid or duplicate strategy ID: {key!r}.")
    _STRATEGIES[key] = strategy_class
    return strategy_class


def get_strategy(strategy_id, **parameters):
    try:
        strategy_class = _STRATEGIES[strategy_id]
    except KeyError as exc:
        raise ValueError(f"Unknown strategy ID: {strategy_id!r}.") from exc
    return strategy_class(**parameters)


def available_strategies():
    return tuple(_STRATEGIES[key] for key in sorted(_STRATEGIES))
