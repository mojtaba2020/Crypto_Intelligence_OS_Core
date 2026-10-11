#!/usr/bin/env python3
"""Fail-closed pre-Fresh-OOS freeze-readiness gate for Challenger V3.

This gate consumes development/validation statistical diagnostics only. It does
not read Fresh Locked OOS, does not crown a champion, and cannot promote to
production. Its sole purpose is to decide whether a candidate is sufficiently
specified and robust to be *eligible for a separate manual freeze decision*.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED_SENSITIVITY_KEYS = (
    "stationary_bootstrap",
    "hac",
    "contiguous_origin_deletion",
    "chronological_regimes",
    "positive_concentration",
)


def evaluate_row(row: dict[str, object]) -> dict[str, object]:
    sensitivity = row.get("sensitivity_diagnostics")
    checks: dict[str, bool] = {
        "inference_eligible": row.get("inference_eligible") is True,
        "development_diagnostic_pass": row.get("diagnostic_pass") is True,
        "positive_mean_improvement": float(row.get("mean_paired_improvement", 0.0)) > 0.0,
        "positive_lower_confidence_bound": (
            float(row.get("one_sided_lower_confidence_bound_95", 0.0)) > 0.0
        ),
        "holm_reject": row.get("holm_reject") is True,
        "sensitivity_packet_complete": isinstance(sensitivity, dict)
        and all(key in sensitivity for key in REQUIRED_SENSITIVITY_KEYS),
    }

    if isinstance(sensitivity, dict):
        deletion = sensitivity.get("contiguous_origin_deletion")
        regimes = sensitivity.get("chronological_regimes")
        concentration = sensitivity.get("positive_concentration")
        checks.update(
            {
                "positive_after_every_tested_origin_deletion": isinstance(deletion, dict)
                and deletion.get("positive_after_every_tested_deletion") is True,
                "all_chronological_thirds_positive": isinstance(regimes, dict)
                and regimes.get("all_thirds_positive") is True,
                "positive_after_top_k_origin_removal": isinstance(concentration, dict)
                and concentration.get("remains_positive_after_top_k_removal") is True,
            }
        )
    else:
        checks.update(
            {
                "positive_after_every_tested_origin_deletion": False,
                "all_chronological_thirds_positive": False,
                "positive_after_top_k_origin_removal": False,
            }
        )

    return {
        "horizon": row.get("horizon"),
        "ablation": row.get("ablation"),
        "candidate": row.get("candidate"),
        "checks": checks,
        "freeze_ready": all(checks.values()),
    }


def evaluate_report(report: dict[str, object]) -> dict[str, object]:
    if report.get("fresh_locked_oos_access") is not False:
        raise ValueError("freeze-readiness input must prove Fresh Locked OOS was not accessed")
    if report.get("v2_locked_oos_used_for_tuning") is not False:
        raise ValueError("freeze-readiness input must prove V2 locked OOS was not used for tuning")
    if report.get("production_promotion") is not False:
        raise ValueError("development report must not authorize production promotion")

    rows = report.get("results")
    if not isinstance(rows, list) or not rows:
        raise ValueError("statistical diagnostic results must be a non-empty list")

    evaluated = [evaluate_row(dict(row)) for row in rows if isinstance(row, dict)]
    if len(evaluated) != len(rows):
        raise ValueError("every statistical result must be an object")

    ready = [row for row in evaluated if row["freeze_ready"]]
    return {
        "status": "CHALLENGER_V3_PRE_FRESH_OOS_FREEZE_READINESS_ONLY",
        "scope": "development_validation_only",
        "criteria_version": "v1",
        "fresh_locked_oos_access": False,
        "v2_locked_oos_used_for_tuning": False,
        "freeze_authorized": False,
        "fresh_oos_authorized": False,
        "champion_authorized": False,
        "production_eligible": False,
        "manual_freeze_decision_required": True,
        "candidate_count": len(evaluated),
        "freeze_ready_candidate_count": len(ready),
        "results": evaluated,
        "policy": (
            "A freeze-ready result is only eligible for a separate manual architecture/model/"
            "feature freeze. No locked outcome may be inspected before that freeze is recorded."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--statistical-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = json.loads(args.statistical_report.read_text(encoding="utf-8"))
    output = evaluate_report(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
