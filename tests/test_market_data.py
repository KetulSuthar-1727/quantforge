
import json
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from engine.market_data import (
    AlpacaMarketDataProvider,
    MarketDataProviderError,
    MarketDataValidationError,
)


@pytest.fixture
def alpaca_provider():
    return AlpacaMarketDataProvider(
        api_key="test-key",
        secret_key="test-secret",
    )


def make_response(payload):
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read.return_value = json.dumps(payload).encode("utf-8")
    return response


def sample_alpaca_bar(timestamp="2026-10-15T14:30:00Z", close=101.0):
    return {
        "t": timestamp,
        "o": 100.0,
        "h": max(102.0, close),
        "l": 99.0,
        "c": close,
        "v": 1200,
    }


def test_alpaca_fetch_bars_normalizes_response(alpaca_provider):
    payload = {"bars": [sample_alpaca_bar()]}

    with patch(
        "engine.market_data.alpaca.urlopen",
        return_value=make_response(payload),
    ):
        result = alpaca_provider.fetch_bars("aapl", "1Min")

    assert list(result.columns) == [
        "Date", "Open", "High", "Low", "Close", "Volume"
    ]
    assert result.iloc[0]["Close"] == 101.0
    assert result.iloc[0]["Volume"] == 1200
    assert str(result["Date"].dt.tz) == "UTC"


def test_alpaca_sends_expected_request_parameters(alpaca_provider):
    with patch(
        "engine.market_data.alpaca.urlopen",
        return_value=make_response({"bars": [sample_alpaca_bar()]}),
    ) as mocked_urlopen:
        alpaca_provider.fetch_bars(
            "aapl",
            "5Min",
            start="2026-10-15T14:00:00Z",
            end="2026-10-15T15:00:00Z",
        )

    request = mocked_urlopen.call_args.args[0]
    parsed = urlparse(request.full_url)
    params = parse_qs(parsed.query)

    assert parsed.path.endswith("/AAPL/bars")
    assert params["timeframe"] == ["5Min"]
    assert params["feed"] == ["iex"]
    assert params["start"] == ["2026-10-15T14:00:00Z"]
    assert params["end"] == ["2026-10-15T15:00:00Z"]
    assert request.get_header("Apca-api-key-id") == "test-key"


def test_alpaca_follows_pagination(alpaca_provider):
    first_page = {
        "bars": [sample_alpaca_bar("2026-10-15T14:30:00Z")],
        "next_page_token": "next-token",
    }
    second_page = {
        "bars": [sample_alpaca_bar("2026-10-15T14:31:00Z", 103.0)],
        "next_page_token": None,
    }

    with patch(
        "engine.market_data.alpaca.urlopen",
        side_effect=[
            make_response(first_page),
            make_response(second_page),
        ],
    ) as mocked_urlopen:
        result = alpaca_provider.fetch_bars("AAPL", "1Min")

    assert len(result) == 2
    assert result.iloc[1]["Close"] == 103.0
    assert mocked_urlopen.call_count == 2
    second_request = mocked_urlopen.call_args_list[1].args[0]
    assert parse_qs(urlparse(second_request.full_url).query)[
        "page_token"
    ] == ["next-token"]


def test_alpaca_rejects_empty_bars(alpaca_provider):
    with patch(
        "engine.market_data.alpaca.urlopen",
        return_value=make_response({"bars": []}),
    ):
        with pytest.raises(MarketDataProviderError, match="no bars"):
            alpaca_provider.fetch_bars("AAPL", "1Min")


@pytest.mark.parametrize("payload", [{"bars": None}, {"bars": [{"t": "2026-10-15T14:30:00Z"}]}])
def test_alpaca_rejects_null_or_incomplete_bar_payload(alpaca_provider, payload):
    with patch(
        "engine.market_data.alpaca.urlopen",
        return_value=make_response(payload),
    ), pytest.raises(MarketDataProviderError):
        alpaca_provider.fetch_bars("AAPL", "1Min")


def test_alpaca_rejects_malformed_response(alpaca_provider):
    with patch(
        "engine.market_data.alpaca.urlopen",
        return_value=make_response({"unexpected": []}),
    ):
        with pytest.raises(MarketDataProviderError, match="valid bars list"):
            alpaca_provider.fetch_bars("AAPL", "1Min")


def test_alpaca_converts_http_errors(alpaca_provider):
    error = HTTPError(
        url="https://data.alpaca.markets/",
        code=401,
        msg="Unauthorized",
        hdrs=None,
        fp=None,
    )

    with patch("engine.market_data.alpaca.urlopen", side_effect=error):
        with pytest.raises(MarketDataProviderError, match="HTTP 401"):
            alpaca_provider.fetch_bars("AAPL", "1Min")


def test_alpaca_rejects_invalid_ohlcv(alpaca_provider):
    invalid_bar = sample_alpaca_bar()
    invalid_bar["h"] = 98.0

    with patch(
        "engine.market_data.alpaca.urlopen",
        return_value=make_response({"bars": [invalid_bar]}),
    ):
        with pytest.raises(MarketDataValidationError):
            alpaca_provider.fetch_bars("AAPL", "1Min")


def test_alpaca_rejects_invalid_interval(alpaca_provider):
    with pytest.raises(ValueError, match="Unsupported interval"):
        alpaca_provider.fetch_bars("AAPL", "2Min")


def test_alpaca_rejects_invalid_symbol(alpaca_provider):
    with pytest.raises(ValueError, match="valid stock ticker"):
        alpaca_provider.fetch_bars("../AAPL", "1Min")


def test_alpaca_rejects_reversed_date_range(alpaca_provider):
    with pytest.raises(ValueError, match="start must be earlier"):
        alpaca_provider.fetch_bars(
            "AAPL",
            "1Min",
            start="2026-10-16T15:00:00Z",
            end="2026-10-16T14:00:00Z",
        )


def test_alpaca_pagination_limit_is_reported(alpaca_provider):
    alpaca_provider.max_pages = 1

    payload = {
        "bars": [sample_alpaca_bar()],
        "next_page_token": "more-data",
    }

    with patch(
        "engine.market_data.alpaca.urlopen",
        return_value=make_response(payload),
    ):
        with pytest.raises(
            MarketDataProviderError,
            match="pagination limit reached",
        ):
            alpaca_provider.fetch_bars("AAPL", "1Min")
