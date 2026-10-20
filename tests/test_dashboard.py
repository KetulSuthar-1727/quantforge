from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest
from unittest.mock import patch

from engine.data import DataHandler
from engine.market_data import MarketDataProviderError

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def dashboard_app():
    app = AppTest.from_file(str(APP_PATH))
    app.default_timeout = 20
    return app.run()


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

    app = dashboard_app()
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

    app = dashboard_app()
    next(
        button for button in app.button
        if button.label == "Run backtest"
    ).click().run()

    assert not app.exception
    assert not any("At least two valid market observations" in item.value for item in app.info)
    assert len(app.dataframe) >= 1

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
        app = dashboard_app()
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
        app = dashboard_app()
        next(
            button for button in app.button
            if button.label == "Fetch market data"
        ).click().run()

    assert not app.exception
    assert any("Market data request failed" in item.value for item in app.error)


def test_backtest_alpaca_fetch_is_only_on_load_action(monkeypatch):
    bars = pd.DataFrame({
        "Date": pd.date_range("2026-01-01", periods=3, freq="D", tz="UTC"),
        "Open": [100.0] * 3, "High": [101.0] * 3, "Low": [99.0] * 3,
        "Close": [100.0, 101.0, 102.0], "Volume": [1000] * 3,
    })
    with patch(
        "engine.market_data.AlpacaMarketDataProvider.__init__",
        return_value=None,
    ), patch(
        "engine.market_data.AlpacaMarketDataProvider.fetch_bars",
        return_value=bars,
    ) as fetch:
        app = dashboard_app()
        assert fetch.call_count == 0
        next(item for item in app.selectbox if item.label == "Historical data source").set_value("Alpaca historical bars").run()
        assert fetch.call_count == 0
        next(button for button in app.button if button.label == "Load selected dataset").click().run()

    assert not app.exception
    assert fetch.call_count == 1
    assert fetch.call_args.kwargs["symbol"] == "AAPL"
    assert fetch.call_args.kwargs["interval"] == "1Day"


def test_dashboard_reruns_do_not_start_scheduled_scans_or_submit_orders():
    with patch("engine.scanner.StockScanner.scan") as scan, patch(
        "engine.paper_trading.OrderManager.submit"
    ) as submit:
        app = dashboard_app()
        app.run()
    assert not app.exception
    scan.assert_not_called()
    submit.assert_not_called()
