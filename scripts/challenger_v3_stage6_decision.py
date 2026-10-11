#!/usr/bin/env python3
"""Record a deterministic Stage-6 research-cycle verdict without accessing locked OOS.

This is an evidence disposition, NOT a model-selection gate or an authorization
for Freeze, Fresh Locked OOS, champion nomination, or production promotion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

try:
    from .challenger_v3_feature_ablation import ABLATIONS
    from .challenger_v3_model_curriculum import HORIZONS
except ImportError:  # direct script execution with scripts/ on sys.path
    from challenger_v3_feature_ablation import ABLATIONS
    from challenger_v3_model_curriculum import HORIZONS

AUDIT_STATUS = "V3_DEVELOPMENT_FAMILY_FAILURE_AUDIT_ONLY"


def _count(value: object, name: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
        raise ValueError(f"invalid {name}")
    return value


def decide_stage6_cycle(audit: dict[str, object]) -> dict[str, object]:
    """Close *this* development falsification cycle; never promote a model."""
    if audit.get("status") != AUDIT_STATUS:
        raise ValueError("input is not an independently checked V3 failure audit")
    for flag in ("fresh_locked_oos_access", "freeze_authorized", "production_promotion"):
        if audit.get(flag) is not False:
            raise ValueError(f"audit must explicitly deny {flag}")
    size = len(HORIZONS) * len(ABLATIONS)
    if audit.get("predeclared_family_size") != size:
        raise ValueError("declared hypothesis family is incomplete")
    eligible = _count(audit.get("eligible_count"), "eligible_count", size)
    positive = _count(audit.get("positive_mean_count"), "positive_mean_count", size)
    ready = _count(audit.get("freeze_ready_count"), "freeze_ready_count", size)
    if ready > eligible or ready > positive:
        raise ValueError("freeze readiness contradicts inference eligibility or positive mean")
    failures = audit.get("failure_counts_by_freeze_check")
    if not isinstance(failures, dict) or not failures:
        raise ValueError("missing scientific failure diagnostics")
    for name, value in failures.items():
        if not isinstance(name, str) or not name:
            raise ValueError("invalid check name")
        _count(value, f"failure count for {name}", size)
    if failures.get("inference_eligible") != size - eligible:
        raise ValueError("inference eligibility failure count contradicts summary")
    if failures.get("positive_mean_improvement") != size - positive:
        raise ValueError("mean improvement failure count contradicts summary")
    horizons = audit.get("per_horizon")
    if not isinstance(horizons, list) or len(horizons) != len(HORIZONS):
        raise ValueError("missing declared horizon-level diagnostics")
    seen: set[str] = set()
    sums = [0, 0, 0]
    for row in horizons:
        if not isinstance(row, dict):
            raise ValueError("invalid horizon diagnostics")
        name = row.get("horizon")
        if name not in HORIZONS or name in seen:
            raise ValueError("duplicate or undeclared horizon")
        seen.add(name)
        if row.get("ablation_count") != len(ABLATIONS):
            raise ValueError("incomplete ablation family")
        _count(row.get("diagnostic_origins"), "diagnostic_origins", 100000)
        for index, field in enumerate(
            (
                "inference_eligible_ablation_count",
                "positive_mean_ablation_count",
                "freeze_ready_ablation_count",
            )
        ):
            sums[index] += _count(row.get(field), field, len(ABLATIONS))
    if tuple(sums) != (eligible, positive, ready):
        raise ValueError("per-horizon totals contradict family summary")

    no_candidate = ready == 0
    return {
        "status": (
            "STAGE6_DEVELOPMENT_FALSIFICATION_CYCLE_CLOSED_NO_GO"
            if no_candidate
            else "STAGE6_READINESS_CANDIDATES_REQUIRE_SEPARATE_MANUAL_REVIEW"
        ),
        "scope": "development_validation_only",
        "stage6_cycle_evidence_review_completed": True,
        "stage6_model_qualification_passed": False if no_candidate else None,
        "stage7_freeze_authorized": False,
        "fresh_locked_oos_access": False,
        "fresh_oos_authorized": False,
        "champion_authorized": False,
        "production_promotion": False,
        "predeclared_hypothesis_count": size,
        "inference_eligible_count": eligible,
        "positive_mean_count": positive,
        "freeze_ready_candidate_count": ready,
        "disposition": (
            "No candidate qualifies. The evaluated Stage-6 cycle has a valid "
            "negative outcome; the project remains blocked at the Stage-7 boundary."
            if no_candidate
            else "Advisory readiness is not Freeze authorization; manual audit and "
            "preregistered freeze review are still required."
        ),
        "next_action": (
            "Preregister fresh, independently assessable development hypotheses; "
            "retain reserved locked data and all original statistical thresholds."
            if no_candidate
            else "Hold manual independent architecture, provenance, leakage and "
            "reproducibility review before any formal Freeze decision."
        ),
        "immutable_guardrails": [
            "no_Fresh_Locked_OOS_access",
            "no_V2_locked_OOS_tuning",
            "no_post_hoc_threshold_reduction",
            "no_automatic_champion_or_production_promotion",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = args.audit_report.read_bytes()
    packet = decide_stage6_cycle(json.loads(raw))
    packet["source_failure_audit_sha256"] = hashlib.sha256(raw).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(packet, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
