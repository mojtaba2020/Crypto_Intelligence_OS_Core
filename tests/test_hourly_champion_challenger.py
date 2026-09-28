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


def test_v3_uses_seven_origin_blocks_and_holm_familywise_gate():
    report = judge(_payload())
    assert report["status"] == "HOURLY_CHAMPION_CHALLENGER_RESEARCH_V3"
    assert report["bootstrap_block_length_origins"] == 7
    assert report["multiple_comparison_method"] == "holm_bonferroni_5_horizons"
    assert report["familywise_alpha"] == 0.05
    assert all(row["statistical_gate"]["block_length"] == 7 for row in report["results"])
    ordered = sorted(
        report["results"],
        key=lambda row: row["statistical_gate"]["holm_rank"],
    )
    assert [row["statistical_gate"]["holm_rank"] for row in ordered] == [1, 2, 3, 4, 5]
    assert [row["statistical_gate"]["holm_threshold"] for row in ordered] == pytest.approx(
        [0.01, 0.0125, 0.05 / 3, 0.025, 0.05]
    )


def test_familywise_gate_is_fail_closed_after_first_holm_failure(monkeypatch):
    probabilities = iter([0.995, 0.98, 0.999, 0.999, 0.999])

    def fake_bootstrap(*args, **kwargs):
        return {
            "paired_samples": 50,
            "mean_loss_improvement": 0.01,
            "ci_95": [0.001, 0.02],
            "bootstrap_probability_improvement_positive": next(probabilities),
            "one_sided_null_centered_p_value": 0.001,
            "block_length": kwargs["block_length"],
            "repetitions": kwargs["repetitions"],
            "gate": "PASS",
        }

    monkeypatch.setattr(
        "scripts.hourly_champion_challenger.paired_block_bootstrap",
        fake_bootstrap,
    )
    report = judge(_payload())
    by_horizon = {row["horizon_hours"]: row for row in report["results"]}
    # Holm ordering is by p-value, not horizon. Once a sorted hypothesis fails,
    # all later hypotheses must remain rejected=False even with smaller-looking
    # unadjusted thresholds downstream.
    ordered = sorted(
        report["results"],
        key=lambda row: row["statistical_gate"]["holm_rank"],
    )
    seen_failure = False
    for row in ordered:
        rejected = row["statistical_gate"]["holm_reject"]
        if seen_failure:
            assert rejected is False
        if not rejected:
            seen_failure = True
    assert all(row["production_promotion"] is False for row in by_horizon.values())


def test_v3_uses_null_centered_p_values_for_holm(monkeypatch):
    pvalues = iter([0.001, 0.02, 0.03, 0.04, 0.05])

    def fake_bootstrap(*args, **kwargs):
        p = next(pvalues)
        return {
            "paired_samples": 50,
            "mean_loss_improvement": 0.01,
            "ci_95": [0.001, 0.02],
            "bootstrap_probability_improvement_positive": 0.999,
            "one_sided_null_centered_p_value": p,
            "block_length": kwargs["block_length"],
            "repetitions": kwargs["repetitions"],
            "gate": "PASS",
        }

    monkeypatch.setattr(
        "scripts.hourly_champion_challenger.paired_block_bootstrap",
        fake_bootstrap,
    )
    report = judge(_payload())
    ordered = sorted(
        report["results"],
        key=lambda row: row["statistical_gate"]["holm_rank"],
    )
    assert ordered[0]["statistical_gate"]["holm_reject"] is True
    assert all(
        row["statistical_gate"]["p_value_method"] == "null_centered_paired_moving_block_bootstrap"
        for row in ordered
    )
    assert all(row["production_promotion"] is False for row in ordered)
