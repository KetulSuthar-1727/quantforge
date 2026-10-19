from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest
from unittest.mock import patch

from engine.data import DataHandler
from engine.market_data import MarketDataProviderError

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def test_dashboard_shows_strategy_and_message_for_single_market_row(monkeypatch):
    one_row = pd.DataFrame({
        "Date": [pd.Timestamp("2026-01-01")],
        "Open": [100.0],
        "High": [100.0],
        "Low": [100.0],
        "Close": [100.0],
        "Volume": [1000],
    })
    monkeypatch.setattr(DataHandler, "load_data", lambda self: one_row.copy())

    app = AppTest.from_file(str(APP_PATH)).run()
    next(
        button for button in app.button
        if button.label == "Run backtest"
    ).click().run()

    assert not app.exception
    assert any("At least two valid market observations" in item.value for item in app.info)
    assert "Final value" in [item.label for item in app.metric]


def test_dashboard_keeps_benchmark_comparison_for_two_market_rows(monkeypatch):
    two_rows = pd.DataFrame({
        "Date": pd.to_datetime(["2026-01-01", "2026-01-02"]),
        "Open": [100.0, 101.0],
        "High": [100.0, 101.0],
        "Low": [100.0, 101.0],
        "Close": [100.0, 101.0],
        "Volume": [1000, 1000],
    })
    monkeypatch.setattr(DataHandler, "load_data", lambda self: two_rows.copy())

    app = AppTest.from_file(str(APP_PATH)).run()
    next(
        button for button in app.button
        if button.label == "Run backtest"
    ).click().run()

    assert not app.exception
    assert not any("At least two valid market observations" in item.value for item in app.info)
    assert len(app.dataframe) == 1

def test_market_data_explorer_displays_fetched_bars(monkeypatch):
    bars = pd.DataFrame({
        "Date": pd.to_datetime(
            ["2026-10-16T14:30:00Z", "2026-10-16T14:35:00Z"],
            utc=True,
        ),
        "Open": [100.0, 101.0],
        "High": [102.0, 103.0],
        "Low": [99.0, 100.0],
        "Close": [101.0, 102.0],
        "Volume": [1000, 1200],
    })

    with patch(
        "engine.market_data.AlpacaMarketDataProvider.__init__",
        return_value=None,
    ), patch(
        "engine.market_data.AlpacaMarketDataProvider.fetch_bars",
        return_value=bars,
    ):
        app = AppTest.from_file(str(APP_PATH)).run()
        next(
            button for button in app.button
            if button.label == "Fetch market data"
        ).click().run()

    assert not app.exception
    assert any("Received 2 bars for AAPL." in item.value for item in app.success)


def test_market_data_explorer_displays_provider_error():
    with patch(
        "engine.market_data.AlpacaMarketDataProvider.fetch_bars",
        side_effect=MarketDataProviderError("Provider unavailable"),
    ):
        app = AppTest.from_file(str(APP_PATH)).run()
        next(
            button for button in app.button
            if button.label == "Fetch market data"
        ).click().run()

    assert not app.exception
    assert any("Market data request failed" in item.value for item in app.error)
