"""Tests for multi-horizon benchmark planning."""

from scripts.evaluate_btc_multihorizon import HORIZONS, plan


def test_supported_horizons_are_ordered_and_complete():
    assert HORIZONS == (1, 3, 7, 14, 21, 30, 90, 180, 365)


def test_plan_uses_longer_windows_for_longer_horizons():
    plans = [plan(horizon) for horizon in HORIZONS]
    holdouts = [holdout for holdout, _step in plans]
    steps = [step for _holdout, step in plans]
    assert holdouts == sorted(holdouts)
    assert all(step >= 1 for step in steps)
    assert plan(365)[1] >= plan(30)[1]
