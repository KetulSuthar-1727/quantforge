import pandas as pd
import pytest

from engine.data import DataHandler


VALID_DATA = {
    "Date": ["2026-01-02", "2026-01-05"],
    "Open": [100, 102],
    "High": [103, 105],
    "Low": [99, 101],
    "Close": [102, 104],
    "Volume": [100000, 120000],
}


def write_csv(tmp_path, data):
    file_path = tmp_path / "market_data.csv"
    pd.DataFrame(data).to_csv(file_path, index=False)
    return file_path


def test_loads_valid_market_data(tmp_path):
    file_path = write_csv(tmp_path, VALID_DATA)

    handler = DataHandler(str(file_path))
    data = handler.load_data()

    assert list(data.columns) == [
        "Date", "Open", "High", "Low", "Close", "Volume"
    ]
    assert len(data) == 2
    assert data["Date"].is_monotonic_increasing


def test_rejects_missing_required_column(tmp_path):
    data = dict(VALID_DATA)
    data.pop("Volume")
    file_path = write_csv(tmp_path, data)

    handler = DataHandler(str(file_path))

    with pytest.raises(ValueError, match="Missing required columns"):
        handler.load_data()


def test_rejects_duplicate_dates(tmp_path):
    data = dict(VALID_DATA)
    data["Date"] = ["2026-01-02", "2026-01-02"]
    file_path = write_csv(tmp_path, data)

    handler = DataHandler(str(file_path))

    with pytest.raises(ValueError, match="Duplicate dates"):
        handler.load_data()


def test_rejects_missing_values(tmp_path):
    data = dict(VALID_DATA)
    data["Close"] = [102, None]
    file_path = write_csv(tmp_path, data)

    handler = DataHandler(str(file_path))

    with pytest.raises(ValueError, match="Missing values"):
        handler.load_data()


def test_rejects_negative_volume(tmp_path):
    data = dict(VALID_DATA)
    data["Volume"] = [100000, -1]
    file_path = write_csv(tmp_path, data)

    handler = DataHandler(str(file_path))

    with pytest.raises(ValueError, match="Volume cannot be negative"):
        handler.load_data()


def test_rejects_high_below_low(tmp_path):
    data = dict(VALID_DATA)
    data["High"] = [98, 105]
    file_path = write_csv(tmp_path, data)

    handler = DataHandler(str(file_path))

    with pytest.raises(ValueError, match="High price cannot be lower than Low price"):
        handler.load_data()


@pytest.mark.parametrize("bad_price", [0, -1])
def test_rejects_nonpositive_prices(tmp_path, bad_price):
    data = dict(VALID_DATA)
    data["Close"] = [102, bad_price]
    file_path = write_csv(tmp_path, data)

    handler = DataHandler(str(file_path))

    with pytest.raises(ValueError):
        handler.load_data()


def test_rejects_close_above_high(tmp_path):
    data = dict(VALID_DATA)
    data["Close"] = [104, 104]
    data["High"] = [103, 105]
    file_path = write_csv(tmp_path, data)

    handler = DataHandler(str(file_path))

    with pytest.raises(ValueError):
        handler.load_data()


def test_rejects_open_below_low(tmp_path):
    data = dict(VALID_DATA)
    data["Open"] = [98, 102]
    file_path = write_csv(tmp_path, data)

    handler = DataHandler(str(file_path))

    with pytest.raises(ValueError):
        handler.load_data()


def test_rejects_infinite_prices(tmp_path):
    data = dict(VALID_DATA)
    data["Close"] = [102, float("inf")]
    file_path = write_csv(tmp_path, data)

    handler = DataHandler(str(file_path))

    with pytest.raises(ValueError):
        handler.load_data()


def test_rejects_nonnumeric_prices(tmp_path):
    data = dict(VALID_DATA)
    data["Close"] = [102, "not-a-price"]
    file_path = write_csv(tmp_path, data)

    handler = DataHandler(str(file_path))

    with pytest.raises(ValueError):
        handler.load_data()
