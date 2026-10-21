import math

import pytest

from engine.metrics import PerformanceMetrics


def metrics(values, dates=None, trades=(), capital=100.0):
    dates = dates or [f"2026-01-{day:02d}" for day in range(1, len(values) + 1)]
    history = [{"date": date, "portfolio_value": value} for date, value in zip(dates, values)]
    return PerformanceMetrics(capital, history, trades, timeframe="1Day")


def test_returns_and_annualization_use_elapsed_dates():
    item = metrics([100, 110], ["2026-01-01", "2027-01-01"])
    assert item.total_return() == pytest.approx(0.1)
    assert item.daily_returns() == pytest.approx([0.1])
    assert item.annualized_return() == pytest.approx(1.1 ** (365.25 / 365) - 1)


def test_empty_and_single_observation_histories():
    assert metrics([]).total_return() is None
    assert metrics([]).cumulative_returns() is None
    single = metrics([125])
    assert single.daily_returns() == []
    assert single.annualized_return() is None
    assert single.annualized_volatility() is None
    assert single.sharpe_ratio() is None
    assert single.sortino_ratio() is None


def test_sharpe_sortino_and_drawdown_conventions():
    item = metrics([100, 110, 99, 108.9])
    returns = item.daily_returns()
    mean = sum(returns) / len(returns)
    sample_sd = (sum((value - mean) ** 2 for value in returns) / (len(returns) - 1)) ** 0.5
    assert item.sharpe_ratio() == pytest.approx(mean / sample_sd * math.sqrt(252))
    downside = (sum(min(value, 0) ** 2 for value in returns) / len(returns)) ** 0.5
    assert item.sortino_ratio() == pytest.approx(mean / downside * math.sqrt(252))
    assert item.drawdowns() == pytest.approx([0, 0, -0.1, -0.01])
    assert item.maximum_drawdown() == pytest.approx(-0.1)


def test_zero_volatility_is_finite_and_zero():
    item = metrics([100, 101, 102.01])
    assert item.sharpe_ratio() is None
    assert item.annualized_volatility() == pytest.approx(0)


def test_fifo_partial_exits_allocate_both_entry_and_exit_costs():
    trades = [
        {"side": "BUY", "quantity": 4, "price": 10, "transaction_cost": 4},
        {"side": "BUY", "quantity": 2, "price": 12, "transaction_cost": 2},
        {"side": "SELL", "quantity": 3, "price": 15, "transaction_cost": 3},
        {"side": "SELL", "quantity": 2, "price": 9, "transaction_cost": 2},
    ]
    item = metrics([100], trades=trades)
    # First sell matches 3 shares of lot one; second matches its remaining
    # share and one share from lot two. Entry and exit costs are per share.
    assert item.trade_pnl() == pytest.approx([9, -3, -5])
    assert item.win_rate() == pytest.approx(1 / 3)
    assert item.average_win() == pytest.approx(9)
    assert item.average_loss() == pytest.approx(-4)
    assert item.profit_factor() == pytest.approx(9 / 8)


def test_open_lots_are_excluded_and_profit_factor_without_losses_is_infinite():
    item = metrics([100], trades=[
        {"side": "BUY", "quantity": 10, "price": 5, "transaction_cost": 1},
        {"side": "SELL", "quantity": 1, "price": 10, "transaction_cost": 0},
    ])
    assert item.trade_pnl() == pytest.approx([4.9])
    assert item.profit_factor() == math.inf
    assert metrics([100]).profit_factor() is None


def test_invalid_capital_dates_and_nonpositive_return_base_are_explicit():
    with pytest.raises(ValueError, match="initial_capital"):
        metrics([1], capital=0)
    with pytest.raises(ValueError, match="invalid date"):
        metrics([100, 101], ["2026-01-01", "not-a-date"]).annualized_return()
    with pytest.raises(ValueError, match="positive prior"):
        metrics([0, 1]).daily_returns()


@pytest.mark.parametrize("ending_value", [0, -10])
def test_annualized_return_rejects_nonpositive_ending_value(ending_value):
    with pytest.raises(ValueError, match="nonpositive final value"):
        metrics([100, ending_value], ["2026-01-01", "2027-01-01"]).annualized_return()


def test_annualized_return_rejects_unsorted_history_dates():
    with pytest.raises(ValueError, match="chronological"):
        metrics([100, 110], ["2026-02-01", "2026-01-01"])


def test_all_loss_trades_have_no_winners_and_zero_profit_factor():
    item = metrics([100], trades=[
        {"side": "BUY", "quantity": 2, "price": 10, "transaction_cost": 0},
        {"side": "SELL", "quantity": 2, "price": 8, "transaction_cost": 0},
    ])
    assert item.trade_pnl() == pytest.approx([-4])
    assert item.win_rate() == 0
    assert item.average_win() is None
    assert item.average_loss() == pytest.approx(-4)
    assert item.profit_factor() == 0


def test_sharpe_subtracts_effective_daily_risk_free_rate():
    item = metrics([100, 110, 110, 104.5])
    returns = item.daily_returns()
    mean = sum(returns) / len(returns)
    deviation = (sum((value - mean) ** 2 for value in returns) / (len(returns) - 1)) ** 0.5
    daily_risk_free = (1.05 ** (1 / 252)) - 1
    expected = (mean - daily_risk_free) / deviation * math.sqrt(252)
    assert item.sharpe_ratio(risk_free_rate=0.05) == pytest.approx(expected)
    assert item.sharpe_ratio(risk_free_rate=0.05) < item.sharpe_ratio()


@pytest.mark.parametrize("values", [[0, 0], [-10, -5], [0, 10], [-5, -2, 10]])
def test_drawdown_requires_a_positive_running_peak(values):
    item = metrics(values)
    with pytest.raises(ValueError, match="positive running portfolio peak"):
        item.drawdowns()
    with pytest.raises(ValueError, match="positive running portfolio peak"):
        item.maximum_drawdown()


def test_drawdown_remains_peak_relative_after_a_positive_peak():
    item = metrics([100, 0, -10, 50])
    assert item.drawdowns() == pytest.approx([0, -1, -1.1, -0.5])
    assert item.maximum_drawdown() == pytest.approx(-1.1)


def test_intraday_annualization_uses_explicit_bar_timeframe():
    item = metrics([100, 101, 100], [
        "2026-01-02T14:30:00", "2026-01-02T14:35:00", "2026-01-02T14:40:00",
    ])
    item.timeframe = "5Min"
    assert item.periods_per_year() == pytest.approx(252 * 78)
    assert item.annualized_volatility() is not None


def test_drawdown_duration_records_recovery_and_current_underwater_period():
    item = metrics([100, 90, 95, 100, 98], [
        "2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05",
    ])
    assert item.drawdown_duration() == {
        "max_observations": 3, "max_days": 3, "current_observations": 1, "current_days": 1,
    }


def test_transaction_costs_turnover_and_missing_exposure():
    item = metrics([100, 110], ["2026-01-01", "2026-01-02"], trades=[
        {"side": "BUY", "quantity": 2, "price": 10, "transaction_cost": 1},
    ])
    assert item.transaction_costs() == 1
    assert item.fees() == 1
    assert item.slippage_cost() is None
    assert item.trade_count() == 1
    assert item.turnover() == pytest.approx(20 / 105)
    assert item.exposure() is None


def test_malformed_history_and_incompatible_benchmark_runs_are_rejected():
    with pytest.raises(ValueError, match="strictly chronological"):
        metrics([100, 101], ["2026-01-01", "2026-01-01"])
    from engine.metrics import compare_runs
    left = {"run_metadata": {"configuration": {"dataset_fingerprint": "a"}}, "portfolio_history": []}
    right = {"run_metadata": {"configuration": {"dataset_fingerprint": "b"}}, "portfolio_history": []}
    with pytest.raises(ValueError, match="fingerprints"):
        compare_runs(left, right)
