#!/usr/bin/env python3
"""Phase 4: pre-registered simple BTC forecasts on chronological matched origins."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import date, timedelta
from itertools import pairwise
from math import exp, isfinite, log
from pathlib import Path

from crypto_intelligence_os.ai_forecasting import Observation


def evaluate(database: Path, *, horizon: int, step: int, holdout_days: int) -> dict:
    if horizon < 1 or step < 1 or holdout_days < horizon + 1:
        raise ValueError("Invalid evaluation window")
    with sqlite3.connect(database) as connection:
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Corrupt price archive")
        rows = connection.execute("SELECT day, price_usd FROM daily_price ORDER BY day").fetchall()
    observations = tuple(Observation(date.fromisoformat(day), float(price)) for day, price in rows)
    if not observations or observations[0].day != date(2011, 1, 1):
        raise ValueError("Incomplete price archive")
    if any(not isfinite(point.close) or point.close <= 0 for point in observations):
        raise ValueError("Invalid daily close")
    if any(b.day - a.day != timedelta(days=1) for a, b in pairwise(observations)):
        raise ValueError("Missing daily close")
    first = max(365, len(observations) - holdout_days)
    last = len(observations) - horizon - 1
    if first > last:
        raise ValueError("No resolved test origins")
    names = ("persistence", "momentum_30d_quarter", "momentum_30d_half", "momentum_90d_quarter")
    errors: dict[str, list[float]] = {name: [] for name in names}
    relative_errors: dict[str, list[float]] = {name: [] for name in names}
    origin_days: list[str] = []
    era_errors: dict[str, dict[str, list[float]]] = {}
    for origin in range(first, last + 1, step):
        current = observations[origin].close
        actual = observations[origin + horizon].close
        # Fixed parameters: no fitting or selection on holdout outcomes.
        trend30 = log(current / observations[origin - 30].close) * horizon / 30
        trend90 = log(current / observations[origin - 90].close) * horizon / 90
        forecasts = (
            current,
            current * exp(max(-1.0, min(1.0, 0.25 * trend30))),
            current * exp(max(-1.0, min(1.0, 0.50 * trend30))),
            current * exp(max(-1.0, min(1.0, 0.25 * trend90))),
        )
        year = observations[origin].day.year
        era = (
            "2012-2016"
            if year <= 2016
            else "2017-2020"
            if year <= 2020
            else "2021-2023"
            if year <= 2023
            else "2024-2026"
        )
        era_values = era_errors.setdefault(era, {name: [] for name in names})
        for name, forecast in zip(names, forecasts, strict=True):
            error = abs(forecast - actual)
            errors[name].append(error)
            relative_errors[name].append(error / current)
            era_values[name].append(error)
        origin_days.append(observations[origin].day.isoformat())
    count = len(origin_days)
    return {
        "status": "PHASE4_FIXED_SIMPLE_WALK_FORWARD",
        "first_data_day": rows[0][0],
        "last_data_day": rows[-1][0],
        "first_test_origin": origin_days[0],
        "last_test_origin": origin_days[-1],
        "horizon_days": horizon,
        "step_days": step,
        "holdout_days": holdout_days,
        "test_examples": count,
        "mae_usd": {name: sum(values) / count for name, values in errors.items()},
        "mean_absolute_error_pct_of_origin_price": {
            name: 100 * sum(values) / count for name, values in relative_errors.items()
        },
        "paired_vs_persistence": {
            name: {
                "mean_error_difference_usd": sum(
                    candidate - baseline
                    for candidate, baseline in zip(values, errors["persistence"], strict=True)
                )
                / count,
                "lower_error_count": sum(
                    candidate < baseline
                    for candidate, baseline in zip(values, errors["persistence"], strict=True)
                ),
                "higher_error_count": sum(
                    candidate > baseline
                    for candidate, baseline in zip(values, errors["persistence"], strict=True)
                ),
            }
            for name, values in errors.items()
            if name != "persistence"
        },
        "by_origin_era": {
            era: {
                "test_examples": len(values["persistence"]),
                "mae_usd": {
                    name: sum(candidate_errors) / len(candidate_errors)
                    for name, candidate_errors in values.items()
                },
                "mean_error_difference_vs_persistence_usd": {
                    name: sum(
                        candidate - baseline
                        for candidate, baseline in zip(
                            candidate_errors, values["persistence"], strict=True
                        )
                    )
                    / len(candidate_errors)
                    for name, candidate_errors in values.items()
                    if name != "persistence"
                },
            }
            for era, values in era_errors.items()
        },
        "research_only": True,
        "limitations": (
            "Fixed untrained candidates; comparisons share identical resolved origins. "
            "Overlapping horizons and historical regime dependence limit inference; "
            "do not choose a winner from this holdout and claim independent validation."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--horizon", type=int, required=True)
    parser.add_argument("--step", type=int, required=True)
    parser.add_argument("--holdout-days", type=int, required=True)
    args = parser.parse_args()
    result = evaluate(
        args.database, horizon=args.horizon, step=args.step, holdout_days=args.holdout_days
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
