#!/usr/bin/env python3
"""Audit only forecasts issued before their target closed; never authorize promotion."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from paired_block_bootstrap import paired_block_bootstrap


def audit(forecasts: list[dict], scores: list[dict], min_resolved: int = 100) -> dict:
    issued = {}
    for row in forecasts:
        key = (row["version"], row["origin_hour_utc"], row["horizon_hours"])
        if key in issued:
            raise ValueError(f"Duplicate forecast: {key}")
        if datetime.fromisoformat(row["issued_at_utc"]) >= datetime.fromisoformat(
            row["target_close_utc"]
        ):
            raise ValueError(f"Forecast issued after target close: {key}")
        issued[key] = row

    groups = defaultdict(list)
    seen = set()
    for row in scores:
        key = (row["version"], row["origin_hour_utc"], row["horizon_hours"])
        if key in seen:
            raise ValueError(f"Duplicate score: {key}")
        seen.add(key)
        forecast = issued.get(key)
        if forecast is None:
            raise ValueError(f"Score without matching issued forecast: {key}")
        if datetime.fromisoformat(row["scored_at_utc"]) < datetime.fromisoformat(
            forecast["target_close_utc"]
        ):
            raise ValueError(f"Score before target close: {key}")
        actual = float(row["actual_close_usd"])
        model_error = abs(float(forecast["forecast_usd"]) - actual)
        baseline_error = abs(float(forecast["persistence_usd"]) - actual)
        if abs(model_error - float(row["model_absolute_error_usd"])) > 0.01:
            raise ValueError(f"Incorrect model score: {key}")
        if abs(baseline_error - float(row["persistence_absolute_error_usd"])) > 0.01:
            raise ValueError(f"Incorrect baseline score: {key}")
        groups[(key[0], key[2])].append(
            (
                forecast["target_hour_utc"],
                model_error,
                baseline_error,
                abs(float(forecast["forecast_usd"]) - float(forecast["persistence_usd"])) > 0.01,
            )
        )

    results = []
    for (version, horizon), rows in sorted(groups.items()):
        rows.sort()
        model = statistics.mean(r[1] for r in rows)
        baseline = statistics.mean(r[2] for r in rows)
        distinct_targets = len({r[0] for r in rows})
        distinct_model_forecasts = sum(row[3] for row in rows)
        results.append(
            {
                "version": version,
                "horizon_hours": horizon,
                "resolved": len(rows),
                "distinct_target_hours": distinct_targets,
                "forecasts_different_from_persistence": distinct_model_forecasts,
                "model_differentiation_observed": distinct_model_forecasts > 0,
                "model_mae_usd": model,
                "persistence_mae_usd": baseline,
                "improvement_pct": 100 * (baseline - model) / baseline if baseline else None,
                "sample_threshold_met": distinct_targets >= min_resolved,
                "statistical_gate": (
                    paired_block_bootstrap(
                        [r[1] for r in rows],
                        [r[2] for r in rows],
                        block_length=min(7, len(rows)),
                    )
                    if distinct_targets >= max(min_resolved, 40)
                    else None
                ),
                "status": "RESEARCH_ONLY_NO_AUTOMATIC_PROMOTION",
            }
        )
    eligible = [row for row in results if row["statistical_gate"] is not None]
    ordered = sorted(eligible, key=lambda row: (
        row["statistical_gate"]["one_sided_null_centered_p_value"],
        row["horizon_hours"],
    ))
    holm_open = True
    for rank, row in enumerate(ordered, start=1):
        gate = row["statistical_gate"]
        threshold = 0.05 / (len(ordered) - rank + 1)
        reject = holm_open and gate["one_sided_null_centered_p_value"] <= threshold
        if not reject:
            holm_open = False
        gate["holm_rank"] = rank
        gate["holm_threshold"] = threshold
        gate["holm_reject"] = reject
        row["prospective_evidence"] = (
            "STATISTICALLY_CONFIRMED_RESEARCH_EDGE"
            if reject and gate["gate"] == "PASS" and row["improvement_pct"] > 0
            else "NO_CONFIRMED_EDGE"
        )

    return {
        "forecast_rows": len(forecasts),
        "scored_rows": len(scores),
        "min_distinct_targets": min_resolved,
        "results": results,
        "multiple_comparison_method": "holm_bonferroni_over_eligible_horizons",
        "familywise_alpha": 0.05,
        "automatic_promotion": False,
        "status": "PROSPECTIVE_STATISTICAL_AUDIT_V2_RESEARCH_ONLY",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forecasts", type=Path, required=True)
    parser.add_argument("--scores", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--min-resolved", type=int, default=100)
    args = parser.parse_args()
    if args.min_resolved < 1:
        parser.error("--min-resolved must be positive")

    def read(path: Path) -> list[dict]:
        if not path.exists():
            return []
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    result = audit(read(args.forecasts), read(args.scores), args.min_resolved)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
