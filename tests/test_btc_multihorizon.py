"""Tests for multi-horizon benchmark planning."""

from scripts.evaluate_btc_multihorizon import HORIZONS, plan, significance_gate


def test_supported_horizons_are_ordered_and_complete():
    assert HORIZONS == (1, 3, 7, 14, 21, 30, 90, 180, 365)


def test_plan_uses_longer_windows_for_longer_horizons():
    plans = [plan(horizon) for horizon in HORIZONS]
    holdouts = [holdout for holdout, _step in plans]
    steps = [step for _holdout, step in plans]
    assert holdouts == sorted(holdouts)
    assert all(step >= 1 for step in steps)
    assert plan(365)[1] >= plan(30)[1]


def _losses(model_error: float, persistence_error: float, count: int = 60):
    return [
        {
            "hybrid_abs_error": model_error + (index % 3) * 0.01,
            "linear_abs_error": model_error + (index % 3) * 0.01,
            "persistence_abs_error": persistence_error + (index % 3) * 0.01,
        }
        for index in range(count)
    ]


def test_significance_gate_passes_clear_paired_improvement():
    result = significance_gate(_losses(1.0, 2.0), "hybrid", horizon=7, step=7)
    assert result["status"] == "PASS"
    assert result["mean_absolute_error_difference_usd"] < 0


def test_significance_gate_rejects_worse_model():
    result = significance_gate(_losses(2.0, 1.0), "linear", horizon=7, step=7)
    assert result["status"] == "FAIL"


def test_significance_gate_requires_minimum_examples():
    result = significance_gate(_losses(1.0, 2.0, count=20), "hybrid", horizon=7, step=7)
    assert result["status"] == "FAIL"
    assert result["examples"] == 20
