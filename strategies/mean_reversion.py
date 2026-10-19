"""Close-based mean-reversion candidate strategy."""
import numpy as np

from engine.strategy import Strategy, register_strategy


@register_strategy
class MeanReversionStrategy(Strategy):
    strategy_id = "mean_reversion"
    version = "1.0"
    name = "Mean reversion"
    description = "Signals after close departs from its rolling mean by a z-score threshold."
    default_parameters = {"window": 20, "entry_zscore": 2.0}

    def __init__(self, window=20, entry_zscore=2.0):
        super().__init__(window=window, entry_zscore=entry_zscore)
        self.window = self.parameters["window"]
        self.entry_zscore = self.parameters["entry_zscore"]

    @classmethod
    def validate_parameters(cls, parameters):
        window, threshold = parameters["window"], parameters["entry_zscore"]
        if isinstance(window, bool) or not isinstance(window, int) or window < 2:
            raise ValueError("window must be an integer of at least 2.")
        if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not np.isfinite(threshold) or threshold <= 0:
            raise ValueError("entry_zscore must be a finite positive number.")

    @property
    def required_lookback(self):
        return self.window

    def generate_signal(self, data):
        result = data.copy()
        close = result["Close"]
        mean = close.rolling(self.window, min_periods=self.window).mean()
        deviation = close.rolling(self.window, min_periods=self.window).std(ddof=0)
        zscore = (close - mean) / deviation.replace(0, np.nan)
        result["signal"] = "HOLD"
        result["signal_strength"] = 0.0
        buy = zscore <= -self.entry_zscore
        sell = zscore >= self.entry_zscore
        result.loc[buy, "signal"] = "BUY"
        result.loc[sell, "signal"] = "SELL"
        result.loc[buy | sell, "signal_strength"] = 1.0
        return result
