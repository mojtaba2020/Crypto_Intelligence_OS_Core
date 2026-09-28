"""Tests for fail-closed hourly model registry."""
from scripts.build_hourly_model_registry import build, HORIZONS

def judge(decision="KEEP_PERSISTENCE_CHAMPION"):
    return {"results":[{"horizon_hours":h,"selected_on_validation":"ridge","decision":decision} for h in HORIZONS]}

def test_registry_falls_back_without_prospective_confirmation():
    out=build(judge("CHALLENGER_ELIGIBLE_FOR_FURTHER_VALIDATION"))
    assert all(r["champion"]=="persistence" and not r["live_authorized"] for r in out["entries"])

def test_registry_requires_both_gates():
    prospective={"results":[{"version":"v","horizon_hours":h,"prospective_evidence":"STATISTICALLY_CONFIRMED_RESEARCH_EDGE"} for h in HORIZONS]}
    out=build(judge("CHALLENGER_ELIGIBLE_FOR_FURTHER_VALIDATION"),prospective)
    assert all(r["champion"]=="ridge" and r["live_authorized"] for r in out["entries"])
