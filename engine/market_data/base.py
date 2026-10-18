from abc import ABC, abstractmethod
from typing import Optional

import pandas as pd


class MarketDataProvider(ABC):
    """Interface implemented by external market-data providers."""

    @abstractmethod
    def fetch_bars(
        self,
        symbol: str,
        interval: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> pd.DataFrame:
        """Fetch OHLCV bars for a symbol and interval.

        The returned DataFrame must use the canonical columns:
        Date, Open, High, Low, Close, Volume.

        Date timestamps must be interpretable as timestamps, and
        provider responses must be normalized and validated before
        being exposed to application code.
        """
        raise NotImplementedError