import numpy as np
import pandas as pd

class DataHandler:
    REQUIRED_COLUMNS = ["Date", "Open", "High", "Low", "Close", "Volume"]
    PRICE_COLUMNS = ["Open", "High", "Low", "Close"]
    NUMERIC_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]

    def __init__(self, file_path):
        self.file_path = file_path
        self.data = None

    def load_data(self):
        self.data = pd.read_csv(self.file_path)

        self.validate_data()

        self.data["Date"] = pd.to_datetime(
            self.data["Date"], errors="raise"
        )

        self.data = self.data.sort_values("Date")
        self.data = self.data.reset_index(drop=True)

        if self.data["Date"].duplicated().any():
            raise ValueError("Duplicate dates found in market data.")

        return self.data

    def validate_data(self):
        missing_columns = [
            column
            for column in self.REQUIRED_COLUMNS
            if column not in self.data.columns
        ]

        if missing_columns:
            raise ValueError(
                f"Missing required columns: {missing_columns}"
            )

        self.data["Date"] = pd.to_datetime(
            self.data["Date"], errors="raise"
        )

        if self.data["Date"].isnull().any():
            raise ValueError("Missing values found in market data.")

        if self.data["Date"].duplicated().any():
            raise ValueError("Duplicate dates found in market data.")

        if self.data[self.NUMERIC_COLUMNS].isnull().any().any():
            raise ValueError("Missing values found in market data.")

        for column in self.NUMERIC_COLUMNS:
            self.data[column] = pd.to_numeric(
                self.data[column], errors="raise"
            )

        numeric_values = self.data[self.NUMERIC_COLUMNS].to_numpy(
            dtype=float
        )

        if not np.isfinite(numeric_values).all():
            raise ValueError("Market data contains non-finite values.")

        if (self.data[self.PRICE_COLUMNS] <= 0).any().any():
            raise ValueError("Prices must be greater than zero.")

        if (self.data["Volume"] < 0).any():
            raise ValueError("Volume cannot be negative.")

        if (self.data["High"] < self.data["Low"]).any():
            raise ValueError("High price cannot be lower than Low price.")

        if (
            (self.data["High"] < self.data["Open"]).any()
            or (self.data["High"] < self.data["Close"]).any()
            or (self.data["Low"] > self.data["Open"]).any()
            or (self.data["Low"] > self.data["Close"]).any()
        ):
            raise ValueError("OHLC prices are inconsistent.")