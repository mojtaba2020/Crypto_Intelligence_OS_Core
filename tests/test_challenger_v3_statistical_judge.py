from __future__ import annotations

import pytest

from scripts.challenger_v3_statistical_judge import _holm, _mbb


def test_moving_block_bootstrap_is_deterministic() -> None:
    diffs = [0.01, 0.02, -0.005, 0.015, 0.008, 0.012]
    first = _mbb(diffs, block=2, seed=12345)
    second = _mbb(diffs, block=2, seed=12345)
    assert first == second
    p_value, ci = first
    assert 0.0 <= p_value <= 1.0
    assert len(ci) == 2
    assert ci[0] <= ci[1]


def test_moving_block_bootstrap_requires_paired_origins() -> None:
    with pytest.raises(ValueError, match="at least two"):
        _mbb([0.01], block=1, seed=7)


def test_holm_stops_rejecting_after_first_failure() -> None:
    rows = [
        {"p_value": 0.001},
        {"p_value": 0.03},
        {"p_value": 0.04},
    ]
    _holm(rows)
    ordered = sorted(rows, key=lambda row: float(row["p_value"]))
    assert ordered[0]["holm_reject"] is True
    assert ordered[1]["holm_reject"] is False
    assert ordered[2]["holm_reject"] is False


def test_holm_rejects_none_when_smallest_fails() -> None:
    rows = [{"p_value": 0.03}, {"p_value": 0.04}, {"p_value": 0.05}]
    _holm(rows)
    assert all(row["holm_reject"] is False for row in rows)


def test_one_sided_bootstrap_strong_positive_signal_has_small_p_and_positive_ci() -> None:
    diffs = [0.010 + 0.0002 * (i % 5) for i in range(40)]
    p_value, ci = _mbb(diffs, block=4, seed=20261003)
    assert p_value < 0.01
    assert ci[0] > 0.0


def test_one_sided_bootstrap_strong_negative_signal_does_not_pass() -> None:
    diffs = [-0.010 - 0.0002 * (i % 5) for i in range(40)]
    p_value, ci = _mbb(diffs, block=4, seed=20261003)
    assert p_value > 0.5
    assert ci[1] < 0.0
