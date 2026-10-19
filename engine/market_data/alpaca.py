import json
import os
import time
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from .base import MarketDataProvider
from .errors import (
    MarketDataProviderError,
    MarketDataValidationError,
)
from .validation import validate_ohlcv_data


class AlpacaMarketDataProvider(MarketDataProvider):
    """Read-only OHLCV provider using Alpaca's stock market-data API."""

    BASE_URL = "https://data.alpaca.markets/v2/stocks"
    SUPPORTED_INTERVALS = {
        "1Min": "1Min",
        "5Min": "5Min",
        "15Min": "15Min",
        "1Hour": "1Hour",
        "1Day": "1Day",
    }

    MAX_RETRIES = 3
    INITIAL_BACKOFF_SECONDS = 0.5
    RETRYABLE_HTTP_STATUS_CODES = {429, 500, 502, 503, 504}

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        feed: str = "iex",
        timeout: int = 15,
        max_pages: int = 20,
    ):
        self.api_key = api_key or os.getenv("ALPACA_API_KEY")
        self.secret_key = secret_key or os.getenv("ALPACA_SECRET_KEY")
        self.feed = feed
        self.timeout = timeout
        self.max_pages = max_pages

        if not self.api_key or not self.secret_key:
            raise MarketDataProviderError(
                "Alpaca credentials are missing. Configure "
                "ALPACA_API_KEY and ALPACA_SECRET_KEY."
            )

        if feed not in {"iex", "sip", "boats", "overnight"}:
            raise ValueError("Unsupported Alpaca stock-data feed.")

        if timeout <= 0:
            raise ValueError("timeout must be positive.")

        if max_pages < 1:
            raise ValueError("max_pages must be at least 1.")

    @staticmethod
    def _format_timestamp(value: Optional[str], field: str) -> Optional[str]:
        if value is None:
            return None

        try:
            timestamp = pd.Timestamp(value)
            if pd.isna(timestamp):
                raise ValueError("Invalid timestamp.")

            if timestamp.tzinfo is None:
                timestamp = timestamp.tz_localize("UTC")
            else:
                timestamp = timestamp.tz_convert("UTC")

            return timestamp.isoformat().replace("+00:00", "Z")
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"Invalid {field} timestamp.") from exc


    def _get_json(self, url: str) -> dict:
        request = Request(
            url,
            headers={
                "APCA-API-KEY-ID": self.api_key,
                "APCA-API-SECRET-KEY": self.secret_key,
                "Accept": "application/json",
            },
        )

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    payload = json.loads(
                        response.read().decode("utf-8")
                    )

            except HTTPError as exc:
                if (
                    exc.code in self.RETRYABLE_HTTP_STATUS_CODES
                    and attempt < self.MAX_RETRIES
                ):
                    time.sleep(
                        self.INITIAL_BACKOFF_SECONDS * (2 ** attempt)
                    )
                    continue

                raise MarketDataProviderError(
                    f"Alpaca returned HTTP {exc.code}."
                ) from None

            except (URLError, TimeoutError, OSError):
                if attempt < self.MAX_RETRIES:
                    time.sleep(
                        self.INITIAL_BACKOFF_SECONDS * (2 ** attempt)
                    )
                    continue

                raise MarketDataProviderError(
                    "Unable to reach Alpaca market data service."
                ) from None

            except (json.JSONDecodeError, UnicodeDecodeError):
                raise MarketDataProviderError(
                    "Alpaca returned an invalid JSON response."
                ) from None

            if not isinstance(payload, dict):
                raise MarketDataProviderError(
                    "Alpaca returned an unexpected response."
                )

            return payload

        raise MarketDataProviderError(
            "Unable to reach Alpaca market data service."
        )

    def fetch_bars(
        self,
        symbol: str,
        interval: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> pd.DataFrame:
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("symbol must be a non-empty string.")

        if interval not in self.SUPPORTED_INTERVALS:
            raise ValueError(
                "Unsupported interval. Choose from: "
                + ", ".join(self.SUPPORTED_INTERVALS)
            )

        symbol = symbol.strip().upper()
        start_utc = self._format_timestamp(start, "start")
        end_utc = self._format_timestamp(end, "end")

        # Default to the last seven days when no date range is supplied.
        # This also works on weekends and market holidays.
        if start_utc is None and end_utc is None:
            end_timestamp = pd.Timestamp.now(tz="UTC")
            start_timestamp = end_timestamp - pd.Timedelta(days=7)
            start_utc = start_timestamp.isoformat().replace("+00:00", "Z")
            end_utc = end_timestamp.isoformat().replace("+00:00", "Z")

        if start_utc and end_utc:
            if pd.Timestamp(start_utc) > pd.Timestamp(end_utc):
                raise ValueError("start must be earlier than or equal to end.")

        params = {
            "timeframe": self.SUPPORTED_INTERVALS[interval],
            "feed": self.feed,
            "limit": 1000,
            "sort": "asc",
        }

        if start_utc:
            params["start"] = start_utc
        if end_utc:
            params["end"] = end_utc

        next_page_token = None
        pages = 0
        rows = []

        while True:
            query = dict(params)
            if next_page_token:
                query["page_token"] = next_page_token

            url = (
                f"{self.BASE_URL}/{symbol}/bars?"
                f"{urlencode(query)}"
            )
            payload = self._get_json(url)

            if "bars" not in payload:
                raise MarketDataProviderError(
                    "Alpaca response does not contain a valid bars list."
                )

            bars = payload["bars"]

            # Alpaca can return null when the requested range has no data.
            if bars is None:
                bars = []
            elif not isinstance(bars, list):
                raise MarketDataProviderError(
                    "Alpaca response does not contain a valid bars list."
                )

            for bar in bars:
                if not isinstance(bar, dict):
                    raise MarketDataProviderError(
                        "Alpaca returned a malformed bar."
                    )

                try:
                    rows.append(
                        {
                            "Date": bar["t"],
                            "Open": bar["o"],
                            "High": bar["h"],
                            "Low": bar["l"],
                            "Close": bar["c"],
                            "Volume": bar["v"],
                        }
                    )
                except KeyError:
                    raise MarketDataProviderError(
                        "Alpaca returned a bar missing required fields."
                    ) from None

            pages += 1
            next_page_token = payload.get("next_page_token")

            if not next_page_token:
                break

            if pages >= self.max_pages:
                raise MarketDataProviderError(
                    "Alpaca pagination limit reached; results are incomplete."
                )

        if not rows:
            raise MarketDataProviderError(
                f"Alpaca returned no bars for {symbol}."
            )

        return validate_ohlcv_data(pd.DataFrame(rows))
