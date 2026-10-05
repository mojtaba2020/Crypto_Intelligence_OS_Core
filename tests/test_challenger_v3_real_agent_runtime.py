import json
from pathlib import Path

import pytest

from scripts.challenger_v3_real_agent_runtime import load_context, validate_envelope, validate_task


def task():
    return {"task_id": "STATS-01", "role": "statistics", "scope": "development_validation_only"}


def packet():
    return {
        "agent_id": "V3-STATS", "agent_version": "1", "role": "statistics", "task_id": "STATS-01",
        "created_at_utc": "2026-10-05T00:00:00Z", "code_commit": "abc", "protocol_version": "v1",
        "scope": "development_validation_only", "hypothesis": "h", "causal_rationale": "r",
        "input_identities": ["artifact:dev"], "proposed_method": "m", "point_in_time_rule": "pit",
        "implementation_and_test_plan": ["test"], "evidence": [], "counterevidence": [],
        "leakage_checks": [], "failure_modes": [], "reproducibility": {}, "confidence": 0.5,
        "recommendation": "audit", "fresh_locked_oos_access": False,
        "v2_locked_oos_used_for_tuning": False, "freeze_authorized": False, "production_eligible": False,
    }


def test_valid_task_and_envelope():
    validate_task(task())
    validate_envelope(packet(), task())


@pytest.mark.parametrize("field", ["fresh_locked_oos_access", "v2_locked_oos_used_for_tuning", "freeze_authorized", "production_eligible"])
def test_authorization_flags_fail_closed(field):
    p = packet()
    p[field] = True
    with pytest.raises(ValueError):
        validate_envelope(p, task())


def test_wrong_role_rejected():
    t = task()
    t["role"] = "trader"
    with pytest.raises(ValueError):
        validate_task(t)


def test_protected_context_rejected(tmp_path: Path):
    p = tmp_path / "evidence.json"
    p.write_text(json.dumps({"name": "Fresh Locked OOS"}), encoding="utf-8")
    with pytest.raises(ValueError, match="protected evidence"):
        load_context([p])


def test_missing_required_field_rejected():
    p = packet()
    del p["counterevidence"]
    with pytest.raises(ValueError, match="missing required"):
        validate_envelope(p, task())


def test_task_identity_mismatch_rejected():
    p = packet()
    p["task_id"] = "OTHER"
    with pytest.raises(ValueError, match="assigned task"):
        validate_envelope(p, task())
