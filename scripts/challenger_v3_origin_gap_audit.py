#!/usr/bin/env python3
"""Fail-closed descriptive calendar audit for previously observed V3 evidence.

Does not train, re-test hypotheses, inspect locked OOS, or authorize promotion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from datetime import UTC, datetime
from pathlib import Path

try:
    from .challenger_v3_feature_ablation import ABLATIONS
    from .challenger_v3_model_curriculum import HORIZONS
    from .multitimeframe_lab_v1 import SPECS
except ImportError:
    from challenger_v3_feature_ablation import ABLATIONS
    from challenger_v3_model_curriculum import HORIZONS
    from multitimeframe_lab_v1 import SPECS

DAY = 86_400
STAT_STATUS = "CHALLENGER_V3_CORRECTED_NESTED_DEVELOPMENT_STATISTICAL_DIAGNOSTICS_ONLY"


def _date(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=UTC).date().isoformat()


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _calendar(records: list[dict], horizon: str) -> tuple[list[int], list[int], list[int]]:
    origins, targets, indexes = [], [], []
    for record in records:
        origin = record.get("origin_timestamp")
        target = record.get("target_timestamp")
        index = record.get("origin_index")
        if any(isinstance(v, bool) or not isinstance(v, int) for v in (origin, target, index)):
            raise ValueError(f"invalid origin metadata for {horizon}")
        if target <= origin or origin % DAY or target % DAY:
            raise ValueError(f"invalid chronological target for {horizon}")
        origins.append(origin)
        targets.append(target)
        indexes.append(index)
    if not origins or any(
        b <= a for values in (origins, indexes, targets) for a, b in zip(values, values[1:])
    ):
        raise ValueError(f"nonchronological origin calendar for {horizon}")
    return origins, targets, indexes


def audit_origin_gaps(development_dir: Path, statistical_report: Path) -> dict:
    stats = json.loads(statistical_report.read_text(encoding="utf-8"))
    if (
        stats.get("status") != STAT_STATUS
        or stats.get("fresh_locked_oos_access") is not False
        or stats.get("v2_locked_oos_used_for_tuning") is not False
        or stats.get("freeze_authorized") is not False
        or stats.get("confirmatory") is not False
    ):
        raise ValueError("invalid development-only statistical input")
    rows = stats.get("results")
    if not isinstance(rows, list):
        raise ValueError("missing statistical family")
    indexed = {}
    for row in rows:
        key = (row.get("horizon"), row.get("ablation"))
        if key in indexed:
            raise ValueError("duplicate statistical hypothesis")
        indexed[key] = row
    if set(indexed) != {(h, a) for h in HORIZONS for a in ABLATIONS}:
        raise ValueError("incomplete statistical hypothesis family")

    specs = {spec.label: spec for spec in SPECS}
    horizons = []
    for horizon in HORIZONS:
        spec = specs[horizon]
        bar_seconds = DAY if spec.family == "daily" else 7 * DAY
        step = spec.evaluation_step_bars * bar_seconds
        path = development_dir / f"classical-development-{horizon}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        if (
            data.get("status") != "CHALLENGER_V3_CLASSICAL_DEVELOPMENT_VALIDATION_ONLY"
            or data.get("fresh_locked_oos_access") is not False
            or data.get("v2_locked_oos_used_for_tuning") is not False
            or data.get("production_promotion") is not False
            or set(data.get("results", {})) != {horizon}
        ):
            raise ValueError(f"invalid development-only packet for {horizon}")
        horizon_data = data["results"][horizon]
        if (
            horizon_data.get("locked_test_access") is not False
            or horizon_data.get("data_role") != "development_validation_only"
        ):
            raise ValueError(f"locked outcomes or incorrect data scope for {horizon}")
        ablations = horizon_data.get("ablation_metrics")
        if not isinstance(ablations, dict) or set(ablations) != set(ABLATIONS):
            raise ValueError(f"incomplete ablation evidence for {horizon}")

        reference = ablations[ABLATIONS[0]]["origin_level_paired_losses"]
        origins, targets, indexes = _calendar(reference, horizon)
        gaps = []
        for i, (before, after) in enumerate(zip(origins, origins[1:])):
            seconds = after - before
            if seconds != (indexes[i + 1] - indexes[i]) * bar_seconds:
                raise ValueError(f"index/calendar mismatch for {horizon}")
            if seconds < step or seconds % step:
                raise ValueError(f"undeclared origin stride for {horizon}")
            if seconds > step:
                gaps.append(
                    {
                        "prior_origin": _date(before),
                        "next_origin": _date(after),
                        "calendar_days": seconds // DAY,
                        "missing_scheduled_origin_slots": seconds // step - 1,
                    }
                )
        descriptions = []
        for ablation in ABLATIONS:
            report = indexed[horizon, ablation]
            records = ablations[ablation]["origin_level_paired_losses"]
            if _calendar(records, horizon) != (origins, targets, indexes):
                raise ValueError(f"inconsistent ablation origin calendar for {horizon}")
            candidate = report.get("candidate")
            selection = report.get("selection_samples")
            purged = report.get("purged_origin_count")
            if (
                not isinstance(candidate, str)
                or isinstance(selection, bool)
                or not isinstance(selection, int)
                or isinstance(purged, bool)
                or not isinstance(purged, int)
                or selection <= 0
                or purged < 0
                or selection + purged >= len(records)
            ):
                raise ValueError(f"invalid nested metadata for {horizon}/{ablation}")
            diagnostic = records[selection + purged :]
            if len(diagnostic) != report.get("diagnostic_sample_count"):
                raise ValueError("diagnostic count differs from statistical evidence")
            deltas = []
            for record in diagnostic:
                errors = record.get("candidate_errors")
                if not isinstance(errors, dict) or candidate not in errors:
                    raise ValueError("selected candidate loss not recorded")
                persistence = float(record["persistence_error"])
                model = float(errors[candidate])
                if not math.isfinite(persistence) or not math.isfinite(model):
                    raise ValueError("nonfinite paired loss")
                if min(persistence, model) < 0:
                    raise ValueError("negative paired loss")
                deltas.append(persistence - model)
            mean = statistics.fmean(deltas)
            if not math.isclose(
                mean, float(report["mean_paired_improvement"]), abs_tol=1e-12, rel_tol=0
            ):
                raise ValueError("reconstructed diagnostic mean contradicts report")
            ordered = sorted(deltas, reverse=True)
            descriptions.append(
                {
                    "ablation": ablation,
                    "nested_selected_candidate": candidate,
                    "diagnostic_count": len(deltas),
                    "mean_paired_improvement": mean,
                    "positive_origin_count": sum(x > 0 for x in deltas),
                    "negative_origin_count": sum(x < 0 for x in deltas),
                    "mean_without_three_largest_positive_deltas_exploratory": (
                        statistics.fmean(ordered[3:]) if len(ordered) > 3 else None
                    ),
                    "inference_eligible": report.get("inference_eligible"),
                    "holm_reject": report.get("holm_reject"),
                }
            )
        horizons.append(
            {
                "horizon": horizon,
                "source_evidence_sha256": _hash(path),
                "evaluation_step_days": step // DAY,
                "evaluated_origins": len(origins),
                "first_origin": _date(origins[0]),
                "last_origin": _date(origins[-1]),
                "last_target_maturity": _date(targets[-1]),
                "calendar_gaps": gaps,
                "missing_scheduled_origin_slots": sum(
                    item["missing_scheduled_origin_slots"] for item in gaps
                ),
                "ablations": descriptions,
            }
        )
    return {
        "status": "V3_DEVELOPMENT_ORIGIN_CALENDAR_AUDIT_EXPLORATORY_ONLY",
        "statistical_evidence_sha256": _hash(statistical_report),
        "hypothesis_count": len(HORIZONS) * len(ABLATIONS),
        "horizons": horizons,
        "fresh_locked_oos_access": False,
        "independent_confirmation": False,
        "freeze_authorized": False,
        "production_promotion": False,
        "interpretation": (
            "Origin-calendar gaps may affect dependence assumptions. "
            "No p-values were re-estimated and this report cannot qualify a model."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--development-dir", type=Path, required=True)
    parser.add_argument("--statistical-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit_origin_gaps(args.development_dir, args.statistical_report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "horizons": len(result["horizons"])}))


if __name__ == "__main__":
    main()
