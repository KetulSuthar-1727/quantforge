import pandas as pd
import pytest

from engine.backtest import BacktestEngine
from engine.costs import TransactionCostModel
from engine.execution import ExecutionEngine
from engine.portfolio import Portfolio
from engine.position_sizing import PositionSizer
from engine.volatility import VolatilityModel


class ControlledStrategy:
    def generate_signal(self, data):
        result = data.copy()
        result["signal"] = ["HOLD", "BUY", "SELL", "BUY"]
        result["signal_strength"] = [0.0, 1.0, 0.0, 0.0]
        return result


class ControlledVolatilityModel:
    def calculate(self, prices, window=20):
        return 0.20


class ControlledPositionSizer:
    def calculate_quantity(
        self,
        available_cash,
        price,
        signal_confidence,
        volatility,
    ):
        return 10 if available_cash > 0 else 0


def test_backtest_executes_trades_and_tracks_portfolio():
    data = pd.DataFrame({
        "Date": pd.date_range("2026-01-01", periods=4, freq="D"),
        "Open": [100.0, 100.0, 110.0, 120.0],
        "High": [100.0, 100.0, 110.0, 120.0],
        "Low": [100.0, 100.0, 110.0, 120.0],
        "Close": [100.0, 100.0, 110.0, 120.0],
        "Volume": [1000, 1000, 1000, 1000],
    })

    portfolio = Portfolio(initial_capital=10000.0)
    cost_model = TransactionCostModel(
        commission_rate=0.001,
        slippage_rate=0.0005,
    )
    execution_engine = ExecutionEngine(portfolio, cost_model)

    engine = BacktestEngine(
        data=data,
        strategy=ControlledStrategy(),
        portfolio=portfolio,
        execution_engine=execution_engine,
        position_sizer=ControlledPositionSizer(),
        volatility_model=ControlledVolatilityModel(),
        symbol="TEST",
    )

    result = engine.run()

    assert len(result["trade_history"]) == 2

    buy, sell = result["trade_history"]

    assert buy["side"] == "BUY"
    assert buy["quantity"] == 10
    assert buy["price"] == 110.0 * 1.0005
    assert buy["transaction_cost"] == 10 * buy["price"] * 0.001

    assert sell["side"] == "SELL"
    assert sell["quantity"] == 10
    assert sell["price"] == 120.0 * 0.9995
    assert sell["transaction_cost"] == 10 * sell["price"] * 0.001

    assert result["position"] == 0
    assert result["portfolio_history"][0]["portfolio_value"] == 10000.0

    cash_after_buy = (
        10000.0
        - 10 * buy["price"]
        - buy["transaction_cost"]
    )
    assert result["portfolio_history"][2]["portfolio_value"] == pytest.approx(
        cash_after_buy + 10 * 110.0
    )
    assert result["cash"] == result["final_value"]
    assert len(result["portfolio_history"]) == len(data)
    assert result["portfolio_history"][-1]["portfolio_value"] == result["final_value"]
    assert result["final_value"] < 10200.0


def test_run_metadata_separates_unique_run_id_from_reproducibility_fingerprint():
    data = pd.DataFrame({
        "Date": pd.date_range("2026-01-01", periods=4, freq="D", tz="UTC"),
        "Open": [100.0] * 4, "High": [100.0] * 4, "Low": [100.0] * 4,
        "Close": [100.0] * 4, "Volume": [1000] * 4,
    })
    class HoldStrategy:
        def __init__(self, window=2, api_secret="must-not-serialize"):
            self.window = window
            self.api_secret = api_secret

        def generate_signal(self, data):
            result = data.copy()
            result["signal"] = "HOLD"
            result["signal_strength"] = 0.0
            return result

    from engine.dataset import create_dataset

    dataset = create_dataset(data, source="csv", symbol="TEST")

    def run(window):
        portfolio = Portfolio(10000.0)
        engine = BacktestEngine(
            dataset.data, HoldStrategy(window), portfolio,
            ExecutionEngine(portfolio, TransactionCostModel()),
            ControlledPositionSizer(), ControlledVolatilityModel(), "TEST",
        )
        return engine.run_with_metadata(dataset.provenance)

    first, second, changed = run(2), run(2), run(3)
    first_meta, second_meta, changed_meta = [
        item["run_metadata"] for item in (first, second, changed)
    ]
    assert first_meta["run_id"] != second_meta["run_id"]
    assert first_meta["reproducibility_fingerprint"] == second_meta["reproducibility_fingerprint"]
    assert first_meta["reproducibility_fingerprint"] != changed_meta["reproducibility_fingerprint"]
    assert "api_secret" not in str(first_meta)
    assert first["final_value"] == second["final_value"]
