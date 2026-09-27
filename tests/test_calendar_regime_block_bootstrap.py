"""Tests for the calendar-preserving regime bootstrap."""

import pytest

from scripts.calendar_regime_block_bootstrap import (
    calendar_regime_block_bootstrap,
)


def test_calendar_regime_bootstrap_is_deterministic_and_passes_clear_edge():
    model = [0.01] * 100
    baseline = [0.02] * 100
    selected = [index % 2 == 0 for index in range(100)]
    first = calendar_regime_block_bootstrap(
        model,
        baseline,
        selected,
        repetitions=500,
    )
    second = calendar_regime_block_bootstrap(
        model,
        baseline,
        selected,
        repetitions=500,
    )
    assert first == second
    assert first["gate"] == "PASS"
    assert first["selected_regime_samples"] == 50
    assert first["ci_95"][0] > 0


def test_calendar_regime_bootstrap_fails_when_there_is_no_edge():
    losses = [0.01] * 100
    selected = [index % 2 == 0 for index in range(100)]
    report = calendar_regime_block_bootstrap(
        losses,
        losses,
        selected,
        repetitions=500,
    )
    assert report["gate"] == "FAIL"
    assert report["ci_95"] == [0.0, 0.0]


def test_calendar_regime_bootstrap_requires_enough_selected_samples():
    with pytest.raises(ValueError, match="at least 40"):
        calendar_regime_block_bootstrap(
            [0.01] * 100,
            [0.02] * 100,
            [index < 39 for index in range(100)],
            repetitions=100,
        )
