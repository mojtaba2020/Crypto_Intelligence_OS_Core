"""Fail-closed tests for independent V3 scientific failure audit."""

from copy import deepcopy

import pytest
from scripts.challenger_v3_failure_audit import audit_failures
from scripts.challenger_v3_feature_ablation import ABLATIONS
from scripts.challenger_v3_model_curriculum import HORIZONS
from scripts.challenger_v3_statistical_judge import HYPOTHESIS_FAMILY_ID


def _reports():
    size = len(HORIZONS) * len(ABLATIONS)
    statistical = {
        "status": "CHALLENGER_V3_CORRECTED_NESTED_DEVELOPMENT_STATISTICAL_DIAGNOSTICS_ONLY",
        "fresh_locked_oos_access": False,
        "v2_locked_oos_used_for_tuning": False,
        "production_promotion": False,
        "freeze_authorized": False,
        "multiplicity": {
            "alpha": 0.05,
            "method": "holm_bonferroni",
            "family_id": HYPOTHESIS_FAMILY_ID,
            "family_size": size,
        },
        "primary_inference": {
            "minimum_diagnostic_origins": 20,
            "method": "studentized_circular_moving_block_bootstrap",
        },
        "results": [],
    }
    freeze = {
        "status": "CHALLENGER_V3_PRE_FRESH_OOS_FREEZE_READINESS_ONLY",
        "fresh_locked_oos_access": False,
        "v2_locked_oos_used_for_tuning": False,
        "freeze_authorized": False,
        "fresh_oos_authorized": False,
        "champion_authorized": False,
        "production_eligible": False,
        "candidate_count": size,
        "freeze_ready_candidate_count": 0,
        "results": [],
    }
    for horizon in HORIZONS:
        for ablation in ABLATIONS:
            base = {"horizon": horizon, "ablation": ablation, "candidate": "ridge"}
            statistical["results"].append(
                {
                    **base,
                    "hypothesis_family_id": HYPOTHESIS_FAMILY_ID,
                    "hypothesis_family_size": size,
                    "dataset_sha256": "a" * 64,
                    "raw_p_value": 1.0,
                    "one_sided_lower_confidence_bound_95": 0.0,
                    "diagnostic_sample_count": 21,
                    "inference_eligible": True,
                    "diagnostic_pass": False,
                    "holm_reject": False,
                    "mean_paired_improvement": -0.01,
                }
            )
            freeze["results"].append(
                {
                    **base,
                    "checks": {
                        "inference_eligible": True,
                        "development_diagnostic_pass": False,
                        "holm_reject": False,
                        "positive_mean_improvement": False,
                    },
                    "freeze_ready": False,
                }
            )
    for rank, row in enumerate(
        sorted(
            statistical["results"],
            key=lambda value: (
                value["raw_p_value"],
                value["horizon"],
                value["ablation"],
            ),
        ),
        1,
    ):
        row["holm_rank"] = rank
        row["holm_threshold"] = 0.05 / (size - rank + 1)
        row["holm_adjusted_p_value"] = 1.0
    return statistical, freeze


def test_audit_covers_full_family_without_authorizing_freeze():
    statistical, freeze = _reports()
    report = audit_failures(statistical, freeze)
    assert report["predeclared_family_size"] == 24
    assert report["eligible_count"] == 24
    assert report["positive_mean_count"] == 0
    assert report["freeze_ready_count"] == 0
    assert report["failure_counts_by_freeze_check"]["holm_reject"] == 24
    assert report["fresh_locked_oos_access"] is False
    assert report["freeze_authorized"] is False


def test_audit_rejects_missing_ablation_instead_of_shrinking_holm_family():
    statistical, freeze = _reports()
    statistical["results"].pop()
    with pytest.raises(ValueError, match="family incomplete"):
        audit_failures(statistical, freeze)


def test_audit_rejects_duplicate_hypothesis():
    statistical, freeze = _reports()
    statistical["results"][1] = deepcopy(statistical["results"][0])
    with pytest.raises(ValueError, match="duplicate hypothesis"):
        audit_failures(statistical, freeze)


def test_audit_rejects_incomplete_multiplicity_metadata():
    statistical, freeze = _reports()
    statistical["multiplicity"]["family_size"] = 4
    with pytest.raises(ValueError, match="protocol mismatch"):
        audit_failures(statistical, freeze)


def test_audit_rejects_candidate_mismatch_between_packets():
    statistical, freeze = _reports()
    freeze["results"][0]["candidate"] = "elastic_net"
    with pytest.raises(ValueError, match="candidate mismatch"):
        audit_failures(statistical, freeze)


def test_audit_rejects_claim_of_eligibility_with_fewer_than_20_origins():
    statistical, freeze = _reports()
    statistical["results"][0]["diagnostic_sample_count"] = 19
    with pytest.raises(ValueError, match="incorrectly marked eligible"):
        audit_failures(statistical, freeze)


def test_audit_rejects_freeze_ready_that_contradicts_checks():
    statistical, freeze = _reports()
    freeze["results"][0]["freeze_ready"] = True
    freeze["freeze_ready_candidate_count"] = 1
    with pytest.raises(ValueError, match="inconsistent with recorded checks"):
        audit_failures(statistical, freeze)


def test_audit_rejects_locked_oos_use():
    statistical, freeze = _reports()
    freeze["fresh_locked_oos_access"] = True
    with pytest.raises(ValueError, match="Fresh Locked OOS"):
        audit_failures(statistical, freeze)


def test_audit_recomputes_holm_adjustment_instead_of_trusting_report():
    statistical, freeze = _reports()
    statistical["results"][0]["holm_adjusted_p_value"] = 0.01
    with pytest.raises(ValueError, match="Holm-adjusted statistics inconsistent"):
        audit_failures(statistical, freeze)


def test_audit_rejects_forged_holm_rejection():
    statistical, freeze = _reports()
    statistical["results"][0]["holm_reject"] = True
    freeze["results"][0]["checks"]["holm_reject"] = True
    with pytest.raises(ValueError, match="Holm-adjusted statistics inconsistent"):
        audit_failures(statistical, freeze)


def test_audit_rejects_nonfinite_p_value():
    statistical, freeze = _reports()
    statistical["results"][0]["raw_p_value"] = float("nan")
    with pytest.raises(ValueError, match="invalid Holm raw p-value"):
        audit_failures(statistical, freeze)


def test_audit_rejects_false_diagnostic_pass():
    statistical, freeze = _reports()
    statistical["results"][0]["diagnostic_pass"] = True
    freeze["results"][0]["checks"]["development_diagnostic_pass"] = True
    with pytest.raises(ValueError, match="diagnostic pass contradicts"):
        audit_failures(statistical, freeze)


def test_audit_rejects_inconsistent_dataset_digest_in_same_horizon():
    statistical, freeze = _reports()
    statistical["results"][0]["dataset_sha256"] = "b" * 64
    with pytest.raises(ValueError, match="inconsistent dataset identity"):
        audit_failures(statistical, freeze)
