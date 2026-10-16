from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

from engine.data import DataHandler

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
    app.button[0].click().run()

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
    app.button[0].click().run()

    assert not app.exception
    assert not any("At least two valid market observations" in item.value for item in app.info)
    assert len(app.dataframe) == 1
