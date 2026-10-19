"""Backward-compatible CSV loader using the shared OHLCV validation boundary."""

import pandas as pd

from engine.market_data import validate_ohlcv_data


class DataHandler:
    REQUIRED_COLUMNS = ["Date", "Open", "High", "Low", "Close", "Volume"]
    PRICE_COLUMNS = ["Open", "High", "Low", "Close"]
    NUMERIC_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]

    def __init__(self, file_path):
        self.file_path = file_path
        self.data = None

    def load_data(self):
        try:
            loaded = pd.read_csv(self.file_path)
        except (OSError, pd.errors.ParserError, UnicodeDecodeError) as exc:
            raise ValueError(f"Could not read market data CSV '{self.file_path}': {exc}") from exc
        self.data = validate_ohlcv_data(loaded)
        return self.data.copy()

    def validate_data(self):
        if self.data is None:
            raise ValueError("No market data has been loaded.")
        self.data = validate_ohlcv_data(self.data)
