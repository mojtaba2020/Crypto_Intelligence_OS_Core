"""Tests for the fail-closed hourly Champion/Challenger judge."""

import copy

import pytest
from scripts.hourly_champion_challenger import CANDIDATES, HORIZONS, judge


def _payload() -> dict:
    rows = []
    for horizon in HORIZONS:
        for origin in range(50):
            rows.append(
                {
                    "horizon_hours": horizon,
                    "origin": origin,
                    "split": "validation",
                    "losses": {
                        "persistence": 0.03,
                        "ridge": 0.02,
                        "extra_trees": 0.025,
                        "boosting": 0.027,
                    },
                }
            )
        for origin in range(100, 150):
            rows.append(
                {
                    "horizon_hours": horizon,
                    "origin": origin,
                    "split": "locked_test",
                    "losses": {
                        "persistence": 0.03,
                        "ridge": 0.02,
                        "extra_trees": 0.01,
                        "boosting": 0.027,
                    },
                }
            )
    return {
        "horizons_hours": list(HORIZONS),
        "candidates": list(CANDIDATES),
        "benchmark": "persistence",
        "validation_end_origin": 49,
        "locked_test_start_origin": 100,
        "rows": rows,
    }


def test_locked_test_cannot_change_selected_challenger():
    payload = _payload()
    before = judge(payload)
    mutated = copy.deepcopy(payload)
    for row in mutated["rows"]:
        if row["split"] == "locked_test":
            row["losses"]["ridge"] = 0.9
            row["losses"]["boosting"] = 0.0001
    after = judge(mutated)
    assert [r["selected_on_validation"] for r in before["results"]] == [
        r["selected_on_validation"] for r in after["results"]
    ]


def test_all_hourly_horizons_are_judged_without_auto_promotion():
    report = judge(_payload())
    assert {row["horizon_hours"] for row in report["results"]} == set(HORIZONS)
    assert all(row["selected_on_validation"] == "ridge" for row in report["results"])
    assert all(row["production_promotion"] is False for row in report["results"])
    assert report["locked_test_used_for_selection"] is False


def test_rejects_overlapping_split_boundaries():
    payload = _payload()
    payload["locked_test_start_origin"] = payload["validation_end_origin"]
    with pytest.raises(ValueError, match="chronologically separated"):
        judge(payload)


def test_rejects_candidate_drift():
    payload = _payload()
    payload["candidates"] = ["ridge", "boosting"]
    with pytest.raises(ValueError, match="locked candidate set"):
        judge(payload)
