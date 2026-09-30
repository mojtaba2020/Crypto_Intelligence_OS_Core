from __future__ import annotations

import math

import pytest
from scripts.multitimeframe_judge_v1 import (
    holm_rejections,
    judge_locked,
    null_centered_moving_block_bootstrap,
    select_on_validation,
)
from scripts.multitimeframe_split_v1 import chronological_split, origins_for_phase


def _candles(n: int) -> list[dict[str, float]]:
    rows = []
    for i in range(n):
        close = 100.0 * math.exp(0.001 * i + 0.02 * math.sin(i / 9))
        rows.append(
            {
                "open": close * 0.998,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": 1000.0 + 10.0 * math.cos(i / 5),
            }
        )
    return rows


def test_holm_is_step_down_and_fail_closed_after_first_non_rejection() -> None:
    decisions = holm_rejections({"a": 0.001, "b": 0.02, "c": 0.06})
    assert decisions == {"a": True, "b": True, "c": False}


def test_bootstrap_is_deterministic_and_null_centered() -> None:
    improvements = [0.02 + 0.001 * math.sin(i) for i in range(30)]
    first = null_centered_moving_block_bootstrap(improvements, 4, draws=500)
    second = null_centered_moving_block_bootstrap(improvements, 4, draws=500)
    assert first == second
    assert first["mean_improvement"] > 0.0
    assert 0.0 <= first["p_value"] <= 1.0


def test_validation_selection_then_locked_judge_uses_disjoint_origins() -> None:
    candles = _candles(700)
    split = chronological_split(len(candles), 365, 1)
    validation = origins_for_phase(split, "validation", 10)
    locked = origins_for_phase(split, "locked_test", 10)
    assert max(validation) < min(locked)
    selected, scores = select_on_validation(candles, "daily", 1, validation)
    assert selected in scores
    report = judge_locked(candles, "daily", 1, locked, selected, block_size=4)
    assert report["selected_candidate"] == selected
    assert report["samples"] == len(locked)
    assert len(report["paired_losses"]) == len(locked)
    assert [row["origin"] for row in report["paired_losses"]] == locked
    for row in report["paired_losses"]:
        assert row["improvement"] == pytest.approx(
            row["persistence_loss"] - row["challenger_loss"]
        )
    assert report["production_promotion"] is False


def test_empty_validation_fails_closed() -> None:
    with pytest.raises(ValueError, match="Validation origins"):
        select_on_validation(_candles(700), "daily", 1, [])


def test_locked_judge_fails_closed_on_gap_crossing_evaluation_origin() -> None:
    candles = _candles(700)
    for i, row in enumerate(candles):
        row["timestamp"] = float(i * 86_400)
    candles[601]["timestamp"] += 86_400
    with pytest.raises(ValueError, match="crosses a missing target period"):
        judge_locked(candles, "daily", 1, [600] * 8, "ridge", block_size=4)


def test_validation_tie_break_follows_predeclared_candidate_order(monkeypatch) -> None:
    from scripts import multitimeframe_judge_v1 as judge

    candles = _candles(700)
    split = chronological_split(len(candles), 365, 1)
    validation = origins_for_phase(split, "validation", 10)

    def tied_result(candles, family, horizon, origins, candidate):
        return judge.CandidateResult(
            candidate,
            tuple(origins),
            (0.1,) * len(origins),
            (0.2,) * len(origins),
        )

    monkeypatch.setattr(judge, "_evaluate_candidate", tied_result)
    selected, _ = judge.select_on_validation(candles, "daily", 1, validation)
    assert selected == judge.CANDIDATES[0]
