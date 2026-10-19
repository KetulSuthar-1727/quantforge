import pandas as pd
import pytest

from engine.scanner import StockScanner
from engine.strategy import available_strategies, get_strategy
from engine.universe import StockUniverse
from strategies.mean_reversion import MeanReversionStrategy
from strategies.moving_average import MovingAverageStrategy


def bars(closes):
    return pd.DataFrame({"Date": pd.date_range("2026-01-01", periods=len(closes), tz="UTC"),
                         "Open": closes, "High": closes, "Low": closes,
                         "Close": closes, "Volume": [100] * len(closes)})


def test_registry_and_parameter_validation():
    assert {cls.strategy_id for cls in available_strategies()} == {"moving_average", "mean_reversion"}
    assert get_strategy("moving_average", fast_window=2, slow_window=4).required_lookback == 4
    with pytest.raises(ValueError, match="Unknown strategy"):
        get_strategy("missing")
    with pytest.raises(ValueError, match="smaller"):
        MovingAverageStrategy(4, 4)


def test_universe_normalizes_deduplicates_and_preserves_order():
    assert StockUniverse([" aapl ", "MSFT", "AAPL"]).symbols == ("AAPL", "MSFT")
    with pytest.raises(ValueError):
        StockUniverse([])
    with pytest.raises(ValueError):
        StockUniverse(["../bad"])


def test_scan_isolated_and_ordered_with_fingerprint_and_insufficient_case():
    samples = {"AAPL": bars([5, 4, 3, 2, 1]), "MSFT": bars([2]), "NVDA": "bad"}
    calls = []

    def loader(symbol):
        calls.append(symbol)
        if symbol == "NVDA":
            raise RuntimeError("fixture failure")
        return samples[symbol]

    result = StockScanner(["AAPL", "MSFT", "NVDA"], MovingAverageStrategy(1, 2), loader).scan()
    assert calls == ["AAPL", "MSFT", "NVDA"]
    assert [item["symbol"] for item in result.results] == ["AAPL", "MSFT", "NVDA"]
    assert [item["status"] for item in result.results] == ["evaluated", "insufficient_data", "error"]
    assert result.results[0]["signal"] == "SELL"
    assert result.results[0]["signal_timestamp"] == result.results[0]["data_timestamp"]
    assert result.results[0]["dataset_fingerprint"]
    assert result.summary == {"symbols_scanned": 3, "evaluated": 1, "insufficient_data": 1, "error": 1}


def test_mean_reversion_is_deterministic_and_rejects_invalid_parameters():
    strategy = MeanReversionStrategy(window=3, entry_zscore=1)
    data = bars([10, 10, 10, 1])
    assert strategy.evaluate(data).signal_type.value == "BUY"
    assert strategy.evaluate(data) == strategy.evaluate(data)
    with pytest.raises(ValueError, match="positive"):
        MeanReversionStrategy(3, 0)
