#!/usr/bin/env python3
"""Reproducible, non-selection audit of Challenger V3 pre-freeze failures.

Consumes development/validation evidence only. Never requests locked outcomes,
changes thresholds, ranks challengers, or authorizes Freeze/production.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

try:
    from .challenger_v3_feature_ablation import ABLATIONS
    from .challenger_v3_model_curriculum import HORIZONS
    from .challenger_v3_statistical_judge import (
        ALPHA,
        HYPOTHESIS_FAMILY_ID,
        MIN_DIAGNOSTIC_ORIGINS,
    )
except ImportError:  # direct script execution with scripts/ on sys.path
    from challenger_v3_feature_ablation import ABLATIONS
    from challenger_v3_model_curriculum import HORIZONS
    from challenger_v3_statistical_judge import (
        ALPHA,
        HYPOTHESIS_FAMILY_ID,
        MIN_DIAGNOSTIC_ORIGINS,
    )

EXPECTED_STATUS = "CHALLENGER_V3_CORRECTED_NESTED_DEVELOPMENT_STATISTICAL_DIAGNOSTICS_ONLY"
EXPECTED_FREEZE_STATUS = "CHALLENGER_V3_PRE_FRESH_OOS_FREEZE_READINESS_ONLY"


def _index_rows(rows: object, *, label: str) -> dict[tuple[str, str], dict]:
    if not isinstance(rows, list):
        raise ValueError(f"{label} results must be a list")
    indexed: dict[tuple[str, str], dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"{label} row is not an object")
        horizon, ablation = row.get("horizon"), row.get("ablation")
        if not isinstance(horizon, str) or not isinstance(ablation, str):
            raise ValueError(f"{label} row lacks a horizon/ablation key")
        key = (horizon, ablation)
        if key in indexed:
            raise ValueError(f"{label} has duplicate hypothesis: {key}")
        indexed[key] = row
    expected = {(h, a) for h in HORIZONS for a in ABLATIONS}
    if set(indexed) != expected:
        raise ValueError(f"{label} hypothesis family incomplete or unexpected")
    return indexed



def _verify_holm_family(rows: dict[tuple[str, str], dict], family_size: int) -> None:
    """Independently recompute the declared Holm family without selecting models."""
    ordered = sorted(
        rows.values(),
        key=lambda row: (
            float(row["raw_p_value"]),
            str(row["horizon"]),
            str(row["ablation"]),
        ),
    )
    if len(ordered) != family_size:
        raise ValueError("Holm hypothesis family size mismatch")
    rejecting = True
    running_adjusted = 0.0
    for rank, row in enumerate(ordered, 1):
        key = (row["horizon"], row["ablation"])
        raw = row.get("raw_p_value")
        if (
            isinstance(raw, bool)
            or not isinstance(raw, (int, float))
            or not math.isfinite(raw)
            or not 0.0 <= raw <= 1.0
        ):
            raise ValueError(f"invalid Holm raw p-value at {key}")
        if row.get("inference_eligible") is not True and raw != 1.0:
            raise ValueError(f"ineligible hypothesis must retain p=1 at {key}")
        multiplier = family_size - rank + 1
        threshold = ALPHA / multiplier
        expected_reject = rejecting and raw <= threshold
        running_adjusted = max(running_adjusted, min(1.0, multiplier * raw))
        reported_adjusted = row.get("holm_adjusted_p_value")
        reported_threshold = row.get("holm_threshold")
        if (
            row.get("holm_rank") != rank
            or row.get("holm_reject") is not expected_reject
            or not isinstance(reported_adjusted, (int, float))
            or not math.isfinite(reported_adjusted)
            or not math.isclose(reported_adjusted, running_adjusted, rel_tol=0, abs_tol=1e-12)
            or not isinstance(reported_threshold, (int, float))
            or not math.isfinite(reported_threshold)
            or not math.isclose(reported_threshold, threshold, rel_tol=0, abs_tol=1e-12)
        ):
            raise ValueError(f"Holm-adjusted statistics inconsistent at {key}")
        mean = row.get("mean_paired_improvement")
        lower = row.get("one_sided_lower_confidence_bound_95")
        if (
            isinstance(mean, bool)
            or isinstance(lower, bool)
            or not isinstance(mean, (int, float))
            or not isinstance(lower, (int, float))
            or not math.isfinite(mean)
            or not math.isfinite(lower)
        ):
            raise ValueError(f"invalid scientific diagnostic values at {key}")
        expected_pass = mean > 0.0 and lower > 0.0 and expected_reject
        if row.get("diagnostic_pass") is not expected_pass:
            raise ValueError(f"diagnostic pass contradicts Holm inference at {key}")
        if not expected_reject:
            rejecting = False


def audit_failures(statistical: dict, freeze: dict) -> dict:
    """Fail on malformed/incomplete evidence, never reinterpret p-values."""
    if statistical.get("status") != EXPECTED_STATUS:
        raise ValueError("unexpected statistical report status")
    if freeze.get("status") != EXPECTED_FREEZE_STATUS:
        raise ValueError("unexpected freeze report status")
    for name, report in (("statistical", statistical), ("freeze", freeze)):
        if report.get("fresh_locked_oos_access") is not False:
            raise ValueError(f"{name} must not access Fresh Locked OOS")
        if report.get("v2_locked_oos_used_for_tuning") is not False:
            raise ValueError(f"{name} must not tune on V2 locked OOS")
    if statistical.get("production_promotion") is not False:
        raise ValueError("statistical report must not allow production promotion")
    for forbidden in (
        "freeze_authorized",
        "fresh_oos_authorized",
        "champion_authorized",
        "production_eligible",
    ):
        if freeze.get(forbidden) is not False:
            raise ValueError(f"freeze packet must not authorize {forbidden}")
    if statistical.get("freeze_authorized") is not False:
        raise ValueError("statistical report must not authorize freeze")
    multiplicity = statistical.get("multiplicity")
    primary = statistical.get("primary_inference")
    if not isinstance(multiplicity, dict) or not isinstance(primary, dict):
        raise ValueError("multiplicity and primary-inference metadata are mandatory")
    family_size = len(HORIZONS) * len(ABLATIONS)
    if (
        multiplicity.get("method") != "holm_bonferroni"
        or multiplicity.get("family_id") != HYPOTHESIS_FAMILY_ID
        or multiplicity.get("family_size") != family_size
        or multiplicity.get("alpha") != ALPHA
        or primary.get("minimum_diagnostic_origins") != MIN_DIAGNOSTIC_ORIGINS
        or primary.get("method") != "studentized_circular_moving_block_bootstrap"
    ):
        raise ValueError("predeclared statistical protocol mismatch")

    stats = _index_rows(statistical.get("results"), label="statistical")
    frozen = _index_rows(freeze.get("results"), label="freeze")
    _verify_holm_family(stats, family_size)
    if freeze.get("candidate_count") != family_size:
        raise ValueError("freeze candidate count does not match declared family")

    failing_checks: Counter[str] = Counter()
    per_horizon: list[dict] = []
    total_positive = 0
    total_eligible = 0
    total_ready = 0
    for horizon in HORIZONS:
        horizon_rows = [stats[horizon, abl] for abl in ABLATIONS]
        horizon_ready = 0
        horizon_eligible = 0
        horizon_positive = 0
        horizon_samples: set[int] = set()
        horizon_digests: set[str] = set()
        for ablation in ABLATIONS:
            key = (horizon, ablation)
            st, fr = stats[key], frozen[key]
            if st.get("candidate") != fr.get("candidate"):
                raise ValueError(f"candidate mismatch at {key}")
            if (
                st.get("hypothesis_family_id") != HYPOTHESIS_FAMILY_ID
                or st.get("hypothesis_family_size") != family_size
            ):
                raise ValueError(f"hypothesis multiplicity mismatch at {key}")
            digest = st.get("dataset_sha256")
            if (
                not isinstance(digest, str)
                or len(digest) != 64
                or any(character not in "0123456789abcdef" for character in digest)
            ):
                raise ValueError(f"invalid dataset identity at {key}")
            horizon_digests.add(digest)
            count = st.get("diagnostic_sample_count")
            if not isinstance(count, int) or count < 0:
                raise ValueError(f"invalid sample count at {key}")
            horizon_samples.add(count)
            if st.get("inference_eligible") is True and count < MIN_DIAGNOSTIC_ORIGINS:
                raise ValueError(f"ineligible sample incorrectly marked eligible: {key}")
            mean = st.get("mean_paired_improvement")
            if not isinstance(mean, (int, float)) or not math.isfinite(mean):
                raise ValueError(f"invalid mean paired improvement at {key}")
            checks = fr.get("checks")
            if not isinstance(checks, dict) or not checks:
                raise ValueError(f"missing freeze checks at {key}")
            if (
                checks.get("inference_eligible") is not st.get("inference_eligible")
                or checks.get("development_diagnostic_pass") is not st.get("diagnostic_pass")
                or checks.get("holm_reject") is not st.get("holm_reject")
                or checks.get("positive_mean_improvement") is not (mean > 0.0)
            ):
                raise ValueError(f"freeze/statistical evidence contradiction at {key}")
            if fr.get("freeze_ready") is not all(value is True for value in checks.values()):
                raise ValueError(f"freeze_ready inconsistent with recorded checks at {key}")
            if fr["freeze_ready"]:
                total_ready += 1
                horizon_ready += 1
            if st["inference_eligible"] is True:
                total_eligible += 1
                horizon_eligible += 1
            if mean > 0.0:
                total_positive += 1
                horizon_positive += 1
            failing_checks.update(name for name, passed in checks.items() if passed is not True)
        if len(horizon_digests) != 1:
            raise ValueError(f"inconsistent dataset identity within horizon: {horizon}")
        if len(horizon_samples) != 1:
            raise ValueError(f"inconsistent diagnostic counts within horizon: {horizon}")
        per_horizon.append(
            {
                "horizon": horizon,
                "diagnostic_origins": horizon_samples.pop(),
                "ablation_count": len(horizon_rows),
                "inference_eligible_ablation_count": horizon_eligible,
                "positive_mean_ablation_count": horizon_positive,
                "freeze_ready_ablation_count": horizon_ready,
            }
        )
    if freeze.get("freeze_ready_candidate_count") != total_ready:
        raise ValueError("freeze-ready count contradicts rows")
    return {
        "status": "V3_DEVELOPMENT_FAMILY_FAILURE_AUDIT_ONLY",
        "predeclared_family_size": family_size,
        "eligible_count": total_eligible,
        "positive_mean_count": total_positive,
        "freeze_ready_count": total_ready,
        "failure_counts_by_freeze_check": dict(sorted(failing_checks.items())),
        "per_horizon": per_horizon,
        "fresh_locked_oos_access": False,
        "freeze_authorized": False,
        "production_promotion": False,
        "interpretation": (
            "A passing workflow does not imply a passing scientific hypothesis. "
            "Do not adjust thresholds or select post hoc based on these results."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--statistical-report", type=Path, required=True)
    parser.add_argument("--freeze-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    statistical = json.loads(args.statistical_report.read_text(encoding="utf-8"))
    freeze = json.loads(args.freeze_report.read_text(encoding="utf-8"))
    packet = audit_failures(statistical, freeze)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(packet, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
