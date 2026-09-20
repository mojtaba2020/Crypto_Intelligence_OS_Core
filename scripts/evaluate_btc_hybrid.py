#!/usr/bin/env python3
"""Walk-forward hybrid versus original linear and persistence, with no future labels."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import date, timedelta
from itertools import pairwise
from math import isfinite
from pathlib import Path

from crypto_intelligence_os.ai_forecasting import Observation, predict, train
from crypto_intelligence_os.hybrid_forecasting import predict_hybrid, train_hybrid


def evaluate(
    database: Path, *, horizon: int, holdout_days: int, step: int, ablation: bool = False
) -> dict:
    if horizon < 1 or step < 1 or holdout_days < horizon + 1:
        raise ValueError("Invalid evaluation window")
    with sqlite3.connect(database) as connection:
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("SQLite integrity check failed")
        rows = connection.execute(
            "SELECT day, price_usd, source FROM daily_price ORDER BY day"
        ).fetchall()
        provenance = dict(connection.execute("SELECT key, value FROM provenance"))
    if not rows or rows[0][0] != "2011-01-01":
        raise ValueError("Incomplete historical archive")
    transition = provenance.get("source_transition_day")
    for raw_day, raw_price, source in rows:
        expected = (
            "coinbase:exchange:BTC-USD:1d:close"
            if transition and raw_day >= transition
            else "coinmetrics:btc:PriceUSD:1d"
        )
        if source != expected or not isfinite(float(raw_price)) or float(raw_price) <= 0:
            raise ValueError(f"Invalid price or source on {raw_day}")
    observations = tuple(
        Observation(date.fromisoformat(day), float(price)) for day, price, _ in rows
    )
    for previous, current in pairwise(observations):
        if current.day - previous.day != timedelta(days=1):
            raise ValueError("Missing daily observation")
    first = max(365 + horizon + 365 - 1, len(observations) - holdout_days)
    last = len(observations) - horizon - 1
    errors: list[tuple[float, ...]] = []
    ablation_errors: dict[str, list[float]] = {
        group: [] for group in ("no_halving", "no_extrema", "momentum_only")
    }
    regime_errors: dict[str, list[tuple[float, ...]]] = {
        "up_90d": [],
        "down_90d": [],
        "flat_90d": [],
    }
    era_errors: dict[str, list[tuple[float, ...]]] = {}
    for origin in range(first, last + 1, step):
        history = observations[: origin + 1]
        hybrid = train_hybrid(history, horizon_days=horizon)
        baseline = train(history, horizon_days=horizon)
        if hybrid.last_training_target > history[-1].day:
            raise ValueError("Hybrid future-label leakage")
        actual = observations[origin + horizon].close
        if ablation:
            for group, group_errors in ablation_errors.items():
                variant = train_hybrid(history, horizon_days=horizon, feature_group=group)
                group_errors.append(abs(predict_hybrid(variant, history) - actual))
        predictions = (
            predict_hybrid(hybrid, history),
            predict(baseline, history),
            history[-1].close,
        )
        row = tuple(abs(estimate - actual) for estimate in predictions) + tuple(
            100 * abs(estimate - actual) / actual for estimate in predictions
        )
        errors.append(row)
        change_90d = history[-1].close / history[-91].close - 1
        regime = "up_90d" if change_90d > 0.10 else "down_90d" if change_90d < -0.10 else "flat_90d"
        regime_errors[regime].append(row)
        origin_day = history[-1].day
        era = (
            "2011-2012" if origin_day.year <= 2012
            else "2013-2016" if origin_day.year <= 2016
            else "2017-2020" if origin_day.year <= 2020
            else "2021-2024" if origin_day.year <= 2024
            else "2025-2026"
        )
        era_errors.setdefault(era, []).append(row)
    if not errors:
        raise ValueError("No resolved out-of-sample examples")
    count = len(errors)
    metrics = {}
    for index, name in enumerate(("hybrid", "linear", "persistence")):
        metrics[name] = {
            "mae_usd": sum(row[index] for row in errors) / count,
            "mape_pct": sum(row[index + 3] for row in errors) / count,
        }
    regimes = {
        name: {
            "test_examples": len(group),
            "mae_usd": {
                model: sum(row[index] for row in group) / len(group)
                for index, model in enumerate(("hybrid", "linear", "persistence"))
            },
        }
        for name, group in regime_errors.items()
        if group
    }
    eras = {
        name: {
            "test_examples": len(group),
            "mae_usd": {
                model: sum(row[index] for row in group) / len(group)
                for index, model in enumerate(("hybrid", "linear", "persistence"))
            },
            "mape_pct": {
                model: sum(row[index + 3] for row in group) / len(group)
                for index, model in enumerate(("hybrid", "linear", "persistence"))
            },
        }
        for name, group in era_errors.items()
    }
    return {
        "status": "HYBRID_WALK_FORWARD_EVALUATED",
        "first_day": rows[0][0],
        "last_day": rows[-1][0],
        "horizon_days": horizon,
        "holdout_days": holdout_days,
        "step_days": step,
        "test_examples": count,
        "first_test_origin": observations[first].day.isoformat(),
        "last_test_origin": observations[first + (count - 1) * step].day.isoformat(),
        "source_transition_day": transition,
        "metrics": metrics,
        "regimes": regimes,
        "eras": eras,
        "ablation_mae_usd": (
            {name: sum(values) / len(values) for name, values in ablation_errors.items()}
            if ablation
            else None
        ),
        "regime_definition": "90-day trailing return: >10% up, <-10% down, otherwise flat",
        "research_only": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--horizon", type=int, default=7)
    parser.add_argument("--holdout-days", type=int, default=365)
    parser.add_argument("--step", type=int, default=7)
    parser.add_argument("--ablation", action="store_true")
    args = parser.parse_args()
    report = evaluate(
        args.database,
        horizon=args.horizon,
        holdout_days=args.holdout_days,
        step=args.step,
        ablation=args.ablation,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
