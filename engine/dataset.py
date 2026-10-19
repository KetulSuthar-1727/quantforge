"""Canonical historical dataset loading, validation, and provenance."""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Optional

import pandas as pd

from engine.market_data import AlpacaMarketDataProvider, validate_ohlcv_data

SUPPORTED_TIMEFRAMES = {"1Min", "5Min", "15Min", "1Hour", "1Day"}


@dataclass(frozen=True)
class DatasetProvenance:
    schema_version: str
    source: str
    symbol: Optional[str]
    timeframe: Optional[str]
    requested_start: Optional[str]
    requested_end: Optional[str]
    observed_start: str
    observed_end: str
    bar_count: int
    feed: Optional[str]
    created_at: str
    fingerprint: str
    source_reference: Optional[str] = None

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class HistoricalDataset:
    data: pd.DataFrame
    provenance: DatasetProvenance


def _utc_iso(value):
    if value is None:
        return None
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")
    return timestamp.isoformat().replace("+00:00", "Z")


def dataset_fingerprint(data: pd.DataFrame) -> str:
    """SHA-256 of canonical OHLCV rows sorted by UTC timestamp.

    The canonical schema is Date/Open/High/Low/Close/Volume. Timestamps are
    UTC ISO strings with nanosecond precision and numeric values use their
    exact IEEE-754 hexadecimal representation. Volatile provenance is excluded.
    """
    canonical = validate_ohlcv_data(data)
    rows = []
    for row in canonical.itertuples(index=False, name=None):
        timestamp, *values = row
        rows.append([pd.Timestamp(timestamp).isoformat(), *[float(v).hex() for v in values]])
    payload = json.dumps(
        {"schema": "quantforge-ohlcv-v1", "columns": ["Date", "Open", "High", "Low", "Close", "Volume"], "rows": rows},
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def create_dataset(
    data: pd.DataFrame,
    *,
    source: str,
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
    requested_start: Optional[str] = None,
    requested_end: Optional[str] = None,
    feed: Optional[str] = None,
    source_reference: Optional[str] = None,
) -> HistoricalDataset:
    if source not in {"csv", "alpaca"}:
        raise ValueError("source must be 'csv' or 'alpaca'.")
    if timeframe is not None and (not isinstance(timeframe, str) or timeframe not in SUPPORTED_TIMEFRAMES):
        raise ValueError("Unsupported timeframe. Choose from: " + ", ".join(sorted(SUPPORTED_TIMEFRAMES)))
    if symbol is not None and (
        not isinstance(symbol, str)
        or not re.fullmatch(r"[A-Za-z0-9.-]{1,20}", symbol.strip())
    ):
        raise ValueError("symbol must be a valid stock ticker.")
    start_utc, end_utc = _utc_iso(requested_start), _utc_iso(requested_end)
    if start_utc is not None and end_utc is not None and pd.Timestamp(start_utc) > pd.Timestamp(end_utc):
        raise ValueError("start must be earlier than or equal to end.")
    normalized = validate_ohlcv_data(data)
    provenance = DatasetProvenance(
        schema_version="quantforge-dataset-v1",
        source=source,
        symbol=symbol.strip().upper() if symbol else None,
        timeframe=timeframe,
        requested_start=start_utc,
        requested_end=end_utc,
        observed_start=_utc_iso(normalized.iloc[0]["Date"]),
        observed_end=_utc_iso(normalized.iloc[-1]["Date"]),
        bar_count=len(normalized),
        feed=feed,
        created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        fingerprint=dataset_fingerprint(normalized),
        source_reference=source_reference,
    )
    return HistoricalDataset(normalized, provenance)


def load_csv_dataset(path, *, symbol=None, timeframe="1Day", start=None, end=None):
    path = Path(path)
    try:
        data = pd.read_csv(path)
    except (OSError, pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise ValueError(f"Could not read market data CSV '{path}': {exc}") from exc
    if start is not None or end is not None:
        normalized = validate_ohlcv_data(data)
        if start is not None:
            normalized = normalized[normalized["Date"] >= pd.Timestamp(_utc_iso(start))]
        if end is not None:
            normalized = normalized[normalized["Date"] <= pd.Timestamp(_utc_iso(end))]
        data = normalized
    return create_dataset(
        data, source="csv", symbol=symbol, timeframe=timeframe,
        requested_start=start, requested_end=end, source_reference=str(path.resolve()),
    )


def fetch_alpaca_dataset(
    provider: AlpacaMarketDataProvider,
    *,
    symbol: str,
    interval: str,
    start=None,
    end=None,
) -> HistoricalDataset:
    data = provider.fetch_bars(symbol=symbol, interval=interval, start=start, end=end)
    return create_dataset(
        data, source="alpaca", symbol=symbol, timeframe=interval,
        requested_start=start, requested_end=end, feed=getattr(provider, "feed", None),
    )
