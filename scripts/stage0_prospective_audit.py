#!/usr/bin/env python3
"""Audit only forecasts issued before their target closed; never authorize promotion."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path


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
        groups[(key[0], key[2])].append((forecast["target_hour_utc"], model_error, baseline_error))

    results = []
    for (version, horizon), rows in sorted(groups.items()):
        rows.sort()
        model = statistics.mean(r[1] for r in rows)
        baseline = statistics.mean(r[2] for r in rows)
        distinct_targets = len({r[0] for r in rows})
        results.append(
            {
                "version": version,
                "horizon_hours": horizon,
                "resolved": len(rows),
                "distinct_target_hours": distinct_targets,
                "model_mae_usd": model,
                "persistence_mae_usd": baseline,
                "improvement_pct": 100 * (baseline - model) / baseline if baseline else None,
                "sample_threshold_met": distinct_targets >= min_resolved,
                "status": "RESEARCH_ONLY_NO_AUTOMATIC_PROMOTION",
            }
        )
    return {
        "forecast_rows": len(forecasts),
        "scored_rows": len(scores),
        "min_distinct_targets": min_resolved,
        "results": results,
        "status": "RESEARCH_ONLY_NO_AUTOMATIC_PROMOTION",
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
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []

    result = audit(read(args.forecasts), read(args.scores), args.min_resolved)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
