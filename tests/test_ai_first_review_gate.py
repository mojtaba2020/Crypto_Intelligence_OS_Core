"""Synthetic-only adversarial tests for AI-first review metadata gate."""

from __future__ import annotations

from copy import deepcopy

import pytest
from scripts.ai_first_review_gate import assess_dry_run_fleet, assess_review_packet

SHA = "a" * 40


def _packet() -> dict:
    return {
        "proposal": {
            "author_id": "AI-PROPOSER",
            "task_id": "research_model",
            "code_sha": SHA,
            "scope": "research",
            "claim": "Synthetic feature preflight satisfies its own unit tests",
            "evidence_refs": ["tests/test_synthetic.py"],
        },
        "critique": {
            "reviewer_id": "AI-CRITIC",
            "task_id": "research_model",
            "code_sha": SHA,
            "blockers": [],
            "counterevidence_refs": ["counterexample-test-name"],
        },
        "test_report": {
            "runner_id": "CI-JOB-1",
            "task_id": "research_model",
            "code_sha": SHA,
            "result": "pass",
            "log_ref": "synthetic-ci-run-reference",
        },
    }


def test_complete_metadata_never_authorizes_science_or_deployment() -> None:
    report = assess_review_packet(_packet())
    assert report["status"] == "PACKET_READY_FOR_EXTERNAL_VERIFICATION"
    assert report["gaps"] == []
    assert report["metadata_independently_verified"] is False
    assert report["external_reviewer_authenticated"] is False
    assert report["scientific_run_authorized"] is False
    assert report["freeze_authorized"] is False
    assert report["production_authorized"] is False
    assert report["paid_tools_authorized"] is False
    assert report["live_agents_dispatched"] == 0


def test_proposer_cannot_self_critique_to_pass() -> None:
    packet = _packet()
    packet["critique"]["reviewer_id"] = packet["proposal"]["author_id"]
    result = assess_review_packet(packet)
    assert result["status"] == "BLOCKED"
    assert "reviewer_is_proposer" in result["gaps"]


def test_critic_veto_is_not_overridden_by_green_test_result() -> None:
    packet = _packet()
    packet["critique"]["blockers"] = ["possible lookahead leakage"]
    result = assess_review_packet(packet)
    assert result["status"] == "BLOCKED"
    assert "critic_reported_blockers" in result["gaps"]


@pytest.mark.parametrize("outcome", ["fail", "not_run"])
def test_incomplete_tests_never_count_as_pass(outcome: str) -> None:
    packet = _packet()
    packet["test_report"]["result"] = outcome
    assert "tests_not_passing" in assess_review_packet(packet)["gaps"]


def test_all_missing_evidence_triggers_explicit_gaps() -> None:
    packet = _packet()
    packet["proposal"]["evidence_refs"] = []
    packet["critique"]["counterevidence_refs"] = []
    packet["test_report"]["log_ref"] = None
    gaps = assess_review_packet(packet)["gaps"]
    assert gaps == ["no_evidence_refs", "no_counterevidence_refs", "no_test_log_reference"]


@pytest.mark.parametrize("branch", ["critique", "test_report"])
def test_stale_revision_evidence_fails_closed(branch: str) -> None:
    packet = _packet()
    packet[branch]["code_sha"] = "b" * 40
    with pytest.raises(ValueError, match="same code commit"):
        assess_review_packet(packet)


@pytest.mark.parametrize("sha", ["not-a-sha", "ABC" * 13 + "A", "a" * 41, ""])
def test_invalid_git_identity_rejected(sha: str) -> None:
    packet = _packet()
    packet["proposal"]["code_sha"] = sha
    with pytest.raises(ValueError):
        assess_review_packet(packet)


@pytest.mark.parametrize("scope", ["trading", "deployment", "stage7", 4, None])
def test_non_review_scope_is_not_authorized(scope: object) -> None:
    packet = _packet()
    packet["proposal"]["scope"] = scope
    with pytest.raises(ValueError, match="scope"):
        assess_review_packet(packet)


def test_extra_price_or_execution_fields_are_rejected() -> None:
    packet = _packet()
    packet["authorize_trading"] = True
    with pytest.raises(ValueError, match="schema"):
        assess_review_packet(packet)


def test_extra_proposer_approval_fields_are_rejected() -> None:
    packet = _packet()
    packet["proposal"]["deploy_now"] = True
    with pytest.raises(ValueError, match="schema"):
        assess_review_packet(packet)


@pytest.mark.parametrize("bad", ["I reviewed it", None, 12, ["review"], {"reviewer_id": "x"}])
def test_malformed_review_packet_rejected(bad: object) -> None:
    with pytest.raises(ValueError, match="schema"):
        assess_review_packet(bad)


def test_test_report_failure_and_critic_veto_both_recorded() -> None:
    packet = _packet()
    packet["test_report"]["result"] = "fail"
    packet["critique"]["blockers"] = ["not verified"]
    assert assess_review_packet(packet)["gaps"] == [
        "critic_reported_blockers",
        "tests_not_passing",
    ]


def test_source_packet_is_not_modified() -> None:
    source = _packet()
    saved = deepcopy(source)
    assess_review_packet(source)
    assert source == saved


def test_bounded_evidence_lists_reject_unreviewable_packet() -> None:
    packet = _packet()
    packet["proposal"]["evidence_refs"] = ["x"] * 26
    with pytest.raises(ValueError, match="bounded"):
        assess_review_packet(packet)


def _fleet_manifest() -> dict:
    return {
        "schema_version": 1,
        "mode": "dry_run",
        "max_active_workers": 2,
        "tasks": [
            {"id": "audit_data", "agent_id": "A001", "kind": "data_audit"},
            {
                "id": "research_model",
                "agent_id": "A041",
                "kind": "model_research",
                "depends_on": ["audit_data"],
            },
            {
                "id": "evaluate",
                "agent_id": "A053",
                "kind": "independent_evaluation",
                "depends_on": ["research_model"],
            },
        ],
    }


def _packet_for(task_id: str) -> dict:
    packet = _packet()
    for section in ("proposal", "critique", "test_report"):
        packet[section]["task_id"] = task_id
    return packet


@pytest.mark.parametrize("section", ["critique", "test_report"])
def test_three_roles_must_agree_on_task_identity(section: str) -> None:
    packet = _packet()
    packet[section]["task_id"] = "other_task"
    with pytest.raises(ValueError, match="same task"):
        assess_review_packet(packet)


def test_task_id_rejects_unreviewable_characters() -> None:
    packet = _packet()
    packet["proposal"]["task_id"] = "../secrets"
    with pytest.raises(ValueError, match="task identity"):
        assess_review_packet(packet)


def test_dry_run_fleet_stops_without_any_review_packets() -> None:
    result = assess_dry_run_fleet(_fleet_manifest(), {})
    assert result["status"] == "BLOCKED"
    assert result["blocked_task_ids"] == ["audit_data", "research_model", "evaluate"]
    assert result["planned_waves"][0][0]["id"] == "audit_data"
    assert result["active_workers"] == 0
    assert result["dispatched_tasks"] == 0
    assert result["external_calls"] == 0
    assert result["dispatch_authorized"] is False
    assert result["freeze_authorized"] is False


def test_claimed_full_review_never_dispatches_or_authenticates() -> None:
    names = ("audit_data", "research_model", "evaluate")
    result = assess_dry_run_fleet(_fleet_manifest(), {name: _packet_for(name) for name in names})
    assert result["status"] == "REVIEW_METADATA_READY_FOR_EXTERNAL_VERIFICATION"
    assert result["blocked_task_ids"] == []
    assert result["independent_evidence_authenticated"] is False
    assert result["dispatch_authorized"] is False
    assert result["scientific_run_authorized"] is False
    assert result["active_workers"] == 0


def test_critic_veto_blocks_its_fleet_task_even_when_ci_claims_pass() -> None:
    packets = {name: _packet_for(name) for name in ("audit_data", "research_model", "evaluate")}
    packets["research_model"]["critique"]["blockers"] = ["possible leakage"]
    report = assess_dry_run_fleet(_fleet_manifest(), packets)
    assert report["blocked_task_ids"] == ["research_model"]
    assert report["status"] == "BLOCKED"


def test_reused_claim_for_different_task_rejected() -> None:
    packets = {"audit_data": _packet_for("research_model")}
    with pytest.raises(ValueError, match="task identity does not match"):
        assess_dry_run_fleet(_fleet_manifest(), packets)


def test_unplanned_packet_is_rejected_not_scheduled() -> None:
    with pytest.raises(ValueError, match="Unexpected"):
        assess_dry_run_fleet(_fleet_manifest(), {"unplanned": _packet_for("unplanned")})


def test_invalid_live_fleet_manifest_stays_rejected() -> None:
    manifest = _fleet_manifest()
    manifest["mode"] = "live"
    with pytest.raises(ValueError, match="dry_run"):
        assess_dry_run_fleet(manifest, {})


def test_no_packet_or_manifest_is_modified() -> None:
    manifest = _fleet_manifest()
    packets = {"audit_data": _packet_for("audit_data")}
    old_manifest = deepcopy(manifest)
    old_packets = deepcopy(packets)
    assess_dry_run_fleet(manifest, packets)
    assert manifest == old_manifest
    assert packets == old_packets
