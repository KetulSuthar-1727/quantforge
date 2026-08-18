import pandas as pd


class DataHandler:
    REQUIRED_COLUMNS = ["Date", "Open", "High", "Low", "Close", "Volume"]

    def __init__(self, file_path):
        self.file_path = file_path
        self.data = None

    def load_data(self):
        self.data = pd.read_csv(self.file_path)

        self.data["Date"] = pd.to_datetime(self.data["Date"])

        self.data = self.data.sort_values("Date")
        self.data = self.data.reset_index(drop=True)

        self.validate_data()

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

        if self.data["Date"].duplicated().any():
            raise ValueError("Duplicate dates found in market data.")

        if self.data[self.REQUIRED_COLUMNS[1:]].isnull().any().any():
            raise ValueError("Missing values found in market data.")

        if (self.data["Volume"] < 0).any():
            raise ValueError("Volume cannot be negative.")

        if (self.data["High"] < self.data["Low"]).any():
            raise ValueError("High price cannot be lower than Low price.")

        print("Market data validation successful.")