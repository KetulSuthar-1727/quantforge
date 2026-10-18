import numpy as np
import pandas as pd

from .errors import MarketDataValidationError


REQUIRED_COLUMNS = [
    "Date",
    "Open",
    "High",
    "Low",
    "Close",
    "Volume",
]

PRICE_COLUMNS = ["Open", "High", "Low", "Close"]
NUMERIC_COLUMNS = PRICE_COLUMNS + ["Volume"]


def validate_ohlcv_data(data: pd.DataFrame) -> pd.DataFrame:
    """Return a validated, chronologically sorted OHLCV DataFrame.

    Timestamps are normalized to UTC. The input DataFrame is not
    modified. Extra provider-specific columns are discarded.
    """
    if not isinstance(data, pd.DataFrame):
        raise MarketDataValidationError(
            "Market data must be a pandas DataFrame."
        )

    missing = [
        column
        for column in REQUIRED_COLUMNS
        if column not in data.columns
    ]

    if missing:
        raise MarketDataValidationError(
            f"Missing required columns: {missing}"
        )

    if data.empty:
        raise MarketDataValidationError(
            "Market data contains no bars."
        )

    result = data[REQUIRED_COLUMNS].copy()

    try:
        result["Date"] = pd.to_datetime(
            result["Date"],
            errors="raise",
            utc=True,
        )

        for column in NUMERIC_COLUMNS:
            result[column] = pd.to_numeric(
                result[column],
                errors="raise",
            )
    except (ValueError, TypeError, OverflowError) as exc:
        raise MarketDataValidationError(
            "Market data contains invalid timestamps or numeric values."
        ) from exc

    if result["Date"].isna().any():
        raise MarketDataValidationError(
            "Missing timestamps found in market data."
        )

    if result[NUMERIC_COLUMNS].isna().any().any():
        raise MarketDataValidationError(
            "Missing numeric values found in market data."
        )

    numeric_values = result[NUMERIC_COLUMNS].to_numpy(dtype=float)

    if not np.isfinite(numeric_values).all():
        raise MarketDataValidationError(
            "Market data contains non-finite values."
        )

    if (result[PRICE_COLUMNS] <= 0).any().any():
        raise MarketDataValidationError(
            "Prices must be greater than zero."
        )

    if (result["Volume"] < 0).any():
        raise MarketDataValidationError(
            "Volume cannot be negative."
        )

    if (result["High"] < result["Low"]).any():
        raise MarketDataValidationError(
            "High price cannot be lower than Low price."
        )

    inconsistent = (
        (result["High"] < result["Open"])
        | (result["High"] < result["Close"])
        | (result["Low"] > result["Open"])
        | (result["Low"] > result["Close"])
    )

    if inconsistent.any():
        raise MarketDataValidationError(
            "OHLC prices are inconsistent."
        )

    if result["Date"].duplicated().any():
        raise MarketDataValidationError(
            "Duplicate timestamps found in market data."
        )

    return (
        result.sort_values("Date")
        .reset_index(drop=True)
    )