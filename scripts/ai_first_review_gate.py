"""Fail-closed, offline AI-first review packet checker.

Pure metadata checks only. Reviewer identifiers, links, test results and
commit hashes are claims supplied by the caller, NOT authenticated evidence.
This module cannot authorize runs, trading, a model freeze, or deployment.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

SHA40 = re.compile(r"^[0-9a-f]{40}$")
SCOPES = frozenset({"software", "research", "security"})
FIELDS = frozenset({"proposal", "critique", "test_report"})
PROPOSAL = frozenset({"author_id", "code_sha", "scope", "claim", "evidence_refs"})
CRITIQUE = frozenset({"reviewer_id", "code_sha", "blockers", "counterevidence_refs"})
TESTS = frozenset({"runner_id", "code_sha", "result", "log_ref"})


def _record(value: object, fields: frozenset[str], label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise ValueError(f"{label} must use the exact review schema")
    return value


def _text(value: object, label: str) -> str:
    if type(value) is not str or not value.strip() or len(value) > 256:
        raise ValueError(f"{label} must be a short nonempty string")
    return value


def _strings(value: object, label: str) -> list[str]:
    if type(value) is not list or len(value) > 25:
        raise ValueError(f"{label} must be a bounded list")
    return [_text(item, label) for item in value]


def assess_review_packet(packet: object) -> dict[str, object]:
    """Check claimed review completeness, never confer scientific authorization."""
    data = _record(packet, FIELDS, "packet")
    proposal = _record(data["proposal"], PROPOSAL, "proposal")
    critique = _record(data["critique"], CRITIQUE, "critique")
    tests = _record(data["test_report"], TESTS, "test_report")

    author = _text(proposal["author_id"], "author_id")
    reviewer = _text(critique["reviewer_id"], "reviewer_id")
    _text(tests["runner_id"], "runner_id")
    _text(proposal["claim"], "claim")
    if type(proposal["scope"]) is not str or proposal["scope"] not in SCOPES:
        raise ValueError("Unknown review scope")
    sha = _text(proposal["code_sha"], "proposal.code_sha")
    if not SHA40.fullmatch(sha):
        raise ValueError("Code SHA must be an exact 40-character hexadecimal Git ID")
    for row, label in ((critique, "critique"), (tests, "test_report")):
        if _text(row["code_sha"], f"{label}.code_sha") != sha:
            raise ValueError("All review components must refer to the same code commit")
    evidence = _strings(proposal["evidence_refs"], "evidence_refs")
    blockers = _strings(critique["blockers"], "blockers")
    counterevidence = _strings(critique["counterevidence_refs"], "counterevidence_refs")
    outcome = tests["result"]
    if type(outcome) is not str or outcome not in ("pass", "fail", "not_run"):
        raise ValueError("Unknown test result")
    log_ref = tests["log_ref"]
    if log_ref is not None:
        _text(log_ref, "log_ref")

    gaps: list[str] = []
    if author == reviewer:
        gaps.append("reviewer_is_proposer")
    if not evidence:
        gaps.append("no_evidence_refs")
    if not counterevidence:
        gaps.append("no_counterevidence_refs")
    if blockers:
        gaps.append("critic_reported_blockers")
    if outcome != "pass":
        gaps.append("tests_not_passing")
    if log_ref is None:
        gaps.append("no_test_log_reference")

    return {
        "status": "BLOCKED" if gaps else "PACKET_READY_FOR_EXTERNAL_VERIFICATION",
        "gaps": gaps,
        "metadata_independently_verified": False,
        "external_reviewer_authenticated": False,
        "scientific_run_authorized": False,
        "freeze_authorized": False,
        "production_authorized": False,
        "paid_tools_authorized": False,
        "live_agents_dispatched": 0,
    }
