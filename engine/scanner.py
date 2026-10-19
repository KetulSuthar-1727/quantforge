"""Offline-capable, per-symbol historical strategy scanner."""
from dataclasses import dataclass

from engine.dataset import HistoricalDataset, dataset_fingerprint
from engine.market_data import validate_ohlcv_data
from engine.strategy import Strategy
from engine.universe import StockUniverse


@dataclass(frozen=True)
class ScanResult:
    summary: dict
    results: tuple

    def to_dict(self):
        return {"summary": dict(self.summary), "results": [dict(row) for row in self.results]}


class StockScanner:
    """Loader is called once per symbol and must deliberately acquire/load bars."""
    def __init__(self, universe, strategy, data_loader, *, timeframe="1Day"):
        self.universe = universe if isinstance(universe, StockUniverse) else StockUniverse(universe)
        if not isinstance(strategy, Strategy):
            raise TypeError("strategy must implement the Strategy contract.")
        if not callable(data_loader):
            raise TypeError("data_loader must be callable.")
        self.strategy = strategy
        self.data_loader = data_loader
        self.timeframe = timeframe

    def scan(self):
        results = []
        for symbol in self.universe:
            base = {"symbol": symbol, "strategy_id": self.strategy.strategy_id,
                    "strategy_version": self.strategy.version,
                    "strategy_parameters": dict(self.strategy.parameters),
                    "timeframe": self.timeframe}
            try:
                loaded = self.data_loader(symbol)
                provenance = loaded.provenance if isinstance(loaded, HistoricalDataset) else None
                raw_data = loaded.data if isinstance(loaded, HistoricalDataset) else loaded
                data = validate_ohlcv_data(raw_data)
                fingerprint = provenance.fingerprint if provenance else dataset_fingerprint(data)
                if len(data) < self.strategy.required_lookback:
                    results.append({**base, "status": "insufficient_data", "signal": None,
                                    "signal_timestamp": None, "data_timestamp": data.iloc[-1]["Date"].isoformat(),
                                    "reason": f"Need {self.strategy.required_lookback} bars; received {len(data)}.",
                                    "bar_count": len(data), "dataset_fingerprint": fingerprint})
                    continue
                signal = self.strategy.evaluate(data)
                row = signal.to_dict()
                results.append({**base, "status": "evaluated", "signal": row["signal_type"],
                                "signal_timestamp": row["signal_timestamp"],
                                "data_timestamp": row["data_timestamp"], "reason": row["reason"],
                                "confidence": row["confidence"], "bar_count": len(data),
                                "dataset_fingerprint": fingerprint})
            except Exception as exc:
                results.append({**base, "status": "error", "signal": None,
                                "signal_timestamp": None, "data_timestamp": None,
                                "reason": f"{type(exc).__name__}: {exc}"})
        counts = {status: sum(row["status"] == status for row in results)
                  for status in ("evaluated", "insufficient_data", "error")}
        return ScanResult({"symbols_scanned": len(results), **counts}, tuple(results))
