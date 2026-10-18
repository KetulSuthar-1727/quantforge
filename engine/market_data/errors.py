class MarketDataError(Exception):
    """Base exception for market-data operations."""


class MarketDataValidationError(MarketDataError, ValueError):
    """Raised when market data violates the canonical data contract."""


class MarketDataProviderError(MarketDataError):
    """Raised when a market-data provider cannot return usable data."""