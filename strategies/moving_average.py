import pandas as pd

from engine.strategy import Strategy

class MovingAverageStrategy(Strategy):

    def __init__(self, fast_window=3, slow_window=5):
        self.fast_window = fast_window
        self.slow_window = slow_window

    def generate_signal(self, data):
        data = data.copy()

        data["fast_ma"] = (
            data["Close"]
            .rolling(window=self.fast_window)
            .mean()
        )

        data["slow_ma"] = (
            data["Close"]
            .rolling(window=self.slow_window)
            .mean()
        )

        data["signal"] = "HOLD"

        data.loc[
            data["fast_ma"] > data["slow_ma"],
            "signal"
        ] = "BUY"

        data.loc[
            data["fast_ma"] < data["slow_ma"],
            "signal"
        ] = "SELL"

        return data