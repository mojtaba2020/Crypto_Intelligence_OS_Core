"""No-go or manual review only: never authorize Stage 7 from diagnostic evidence."""

from copy import deepcopy

import pytest

from scripts.challenger_v3_stage6_decision import decide_stage6_cycle


def _audit():
    horizons = ("1d", "2d", "3d", "1w", "2w", "3w")
    rows = []
    for name in horizons:
        eligible = 4 if name in {"1d", "2d", "3d"} else 0
        positive = {"1d": 1, "2d": 3, "3d": 3, "1w": 1, "2w": 0, "3w": 0}[name]
        count = {"1d": 21, "2d": 21, "3d": 21, "1w": 19, "2w": 18, "3w": 18}[name]
        rows.append(
            {
                "horizon": name,
                "ablation_count": 4,
                "diagnostic_origins": count,
                "inference_eligible_ablation_count": eligible,
                "positive_mean_ablation_count": positive,
                "freeze_ready_ablation_count": 0,
            }
        )
    return {
        "status": "V3_DEVELOPMENT_FAMILY_FAILURE_AUDIT_ONLY",
        "fresh_locked_oos_access": False,
        "freeze_authorized": False,
        "production_promotion": False,
        "predeclared_family_size": 24,
        "eligible_count": 12,
        "positive_mean_count": 8,
        "freeze_ready_count": 0,
        "failure_counts_by_freeze_check": {
            "inference_eligible": 12,
            "positive_mean_improvement": 16,
            "holm_reject": 24,
        },
        "per_horizon": rows,
    }


def test_falsified_cycle_is_closed_but_never_authorizes_freeze():
    result = decide_stage6_cycle(_audit())
    assert result["status"] == "STAGE6_DEVELOPMENT_FALSIFICATION_CYCLE_CLOSED_NO_GO"
    assert result["stage6_cycle_evidence_review_completed"] is True
    assert result["stage6_model_qualification_passed"] is False
    assert result["stage7_freeze_authorized"] is False
    assert result["fresh_oos_authorized"] is False
    assert result["freeze_ready_candidate_count"] == 0


def test_readiness_does_not_auto_authorize_stage7():
    audit = _audit()
    audit["per_horizon"][0]["freeze_ready_ablation_count"] = 1
    audit["freeze_ready_count"] = 1
    result = decide_stage6_cycle(audit)
    assert result["status"] == "STAGE6_READINESS_CANDIDATES_REQUIRE_SEPARATE_MANUAL_REVIEW"
    assert result["stage7_freeze_authorized"] is False
    assert result["champion_authorized"] is False


@pytest.mark.parametrize(
    "field", ["fresh_locked_oos_access", "freeze_authorized", "production_promotion"]
)
def test_forbidden_authorization_or_locked_access_is_rejected(field):
    audit = _audit()
    audit[field] = True
    with pytest.raises(ValueError, match=field):
        decide_stage6_cycle(audit)


def test_missing_or_duplicate_horizon_is_rejected():
    audit = _audit()
    audit["per_horizon"][1] = deepcopy(audit["per_horizon"][0])
    with pytest.raises(ValueError, match="duplicate or undeclared horizon"):
        decide_stage6_cycle(audit)


def test_incomplete_ablation_family_is_rejected():
    audit = _audit()
    audit["per_horizon"][2]["ablation_count"] = 3
    with pytest.raises(ValueError, match="incomplete ablation"):
        decide_stage6_cycle(audit)


def test_mismatched_failure_count_is_rejected():
    audit = _audit()
    audit["failure_counts_by_freeze_check"]["inference_eligible"] = 0
    with pytest.raises(ValueError, match="contradicts summary"):
        decide_stage6_cycle(audit)


def test_inconsistent_per_horizon_total_is_rejected():
    audit = _audit()
    audit["per_horizon"][0]["positive_mean_ablation_count"] = 2
    with pytest.raises(ValueError, match="per-horizon totals"):
        decide_stage6_cycle(audit)


def test_bool_count_is_rejected():
    audit = _audit()
    audit["positive_mean_count"] = True
    with pytest.raises(ValueError, match="invalid positive_mean_count"):
        decide_stage6_cycle(audit)
