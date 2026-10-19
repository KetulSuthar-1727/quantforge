import pandas as pd
import pytest

from engine.dataset import (
    create_dataset,
    dataset_fingerprint,
    fetch_alpaca_dataset,
    load_csv_dataset,
)


@pytest.fixture
def bars():
    return pd.DataFrame({
        "Date": ["2026-01-05", "2026-01-02"],
        "Open": [102, 100], "High": [105, 103], "Low": [101, 99],
        "Close": [104, 102], "Volume": [1200, 1000],
    })


def test_fingerprint_is_canonical_and_sensitive_to_data(bars):
    original = dataset_fingerprint(bars)
    assert dataset_fingerprint(bars.iloc[::-1]) == original
    changed = bars.copy()
    changed.loc[0, "Close"] = 103.5
    assert dataset_fingerprint(changed) != original
    changed = bars.copy()
    changed.loc[0, "Date"] = "2026-01-06"
    assert dataset_fingerprint(changed) != original


def test_dataset_keeps_requested_and_observed_ranges_separate(bars):
    dataset = create_dataset(
        bars, source="csv", symbol="aapl", timeframe="1Day",
        requested_start="2026-01-01", requested_end="2026-01-31",
    )
    assert dataset.provenance.requested_start == "2026-01-01T00:00:00Z"
    assert dataset.provenance.observed_start == "2026-01-02T00:00:00Z"
    assert dataset.provenance.observed_end == "2026-01-05T00:00:00Z"
    assert dataset.provenance.symbol == "AAPL"
    assert dataset.provenance.bar_count == 2


def test_csv_loader_filters_explicit_range_and_reports_missing_file(tmp_path, bars):
    path = tmp_path / "bars.csv"
    bars.to_csv(path, index=False)
    dataset = load_csv_dataset(path, start="2026-01-05", end="2026-01-05")
    assert len(dataset.data) == 1
    assert dataset.provenance.requested_start == "2026-01-05T00:00:00Z"
    with pytest.raises(ValueError, match="Could not read market data CSV"):
        load_csv_dataset(tmp_path / "missing.csv")


def test_reversed_range_rejected(bars):
    with pytest.raises(ValueError, match="start must be earlier"):
        create_dataset(bars, source="csv", requested_start="2026-02-01", requested_end="2026-01-01")


def test_alpaca_fetch_is_explicit_and_provenance_has_feed(bars):
    class Provider:
        feed = "iex"

        def __init__(self):
            self.calls = []

        def fetch_bars(self, **kwargs):
            self.calls.append(kwargs)
            return bars

    provider = Provider()
    result = fetch_alpaca_dataset(
        provider, symbol="AAPL", interval="5Min",
        start="2026-01-01T14:30:00Z", end="2026-01-01T15:00:00Z",
    )
    assert provider.calls == [{
        "symbol": "AAPL", "interval": "5Min",
        "start": "2026-01-01T14:30:00Z", "end": "2026-01-01T15:00:00Z",
    }]
    assert result.provenance.source == "alpaca"
    assert result.provenance.feed == "iex"
