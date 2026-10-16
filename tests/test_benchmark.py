import pytest

from engine.benchmark import (
    BuyAndHoldBenchmark,
    has_sufficient_benchmark_history,
)


def test_benchmark_comparison_requires_two_prices():
    assert not has_sufficient_benchmark_history([])
    assert not has_sufficient_benchmark_history([100])
    assert has_sufficient_benchmark_history([100, 101])

    with pytest.raises(ValueError, match="At least two prices"):
        BuyAndHoldBenchmark(1000).run([100], ["2026-01-01"])


def test_benchmark_runs_with_two_observations_and_preserves_dates():
    result = BuyAndHoldBenchmark(1000).run(
        [100, 110], ["2026-01-01", "2026-01-02"]
    )
    assert [item["date"] for item in result["portfolio_history"]] == [
        "2026-01-01", "2026-01-02"
    ]
    assert result["final_value"] == 1100
