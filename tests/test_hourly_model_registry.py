"""Tests for fail-closed hourly model registry."""
from scripts.build_hourly_model_registry import HORIZONS, build


def judge(decision="KEEP_PERSISTENCE_CHAMPION"):
    return {
        "results": [
            {
                "horizon_hours": horizon,
                "selected_on_validation": "ridge",
                "decision": decision,
            }
            for horizon in HORIZONS
        ]
    }


def test_registry_falls_back_without_prospective_confirmation():
    out = build(judge("CHALLENGER_ELIGIBLE_FOR_FURTHER_VALIDATION"))
    assert all(
        row["champion"] == "persistence" and not row["live_authorized"]
        for row in out["entries"]
    )


def test_registry_requires_both_gates():
    prospective = {
        "results": [
            {
                "version": "v",
                "horizon_hours": horizon,
                "prospective_evidence": "STATISTICALLY_CONFIRMED_RESEARCH_EDGE",
            }
            for horizon in HORIZONS
        ]
    }
    out = build(judge("CHALLENGER_ELIGIBLE_FOR_FURTHER_VALIDATION"), prospective)
    assert all(
        row["champion"] == "ridge" and row["live_authorized"] for row in out["entries"]
    )
