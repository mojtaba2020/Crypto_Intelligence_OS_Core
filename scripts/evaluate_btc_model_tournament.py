#!/usr/bin/env python3
"""Research-only BTC model tournament with chronological selection and locked test."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import date, timedelta
from itertools import pairwise
from math import isfinite
from pathlib import Path

from scripts.evaluate_btc_multihorizon import HORIZONS, plan

MODELS = ("persistence", "momentum_30d_quarter", "momentum_90d_quarter")


def predict(name: str, prices: list[float], origin: int, horizon: int) -> float:
    current = prices[origin]
    if name == "persistence":
        return current
    lookback = 30 if name == "momentum_30d_quarter" else 90
    return max(0.01, current + 0.25 * horizon * (current - prices[origin - lookback]) / lookback)


def score(prices: list[float], origins: list[int], horizon: int) -> dict:
    if not origins:
        raise ValueError("No resolved observations in tournament split")
    return {
        name: sum(
            abs(predict(name, prices, origin, horizon) - prices[origin + horizon])
            for origin in origins
        )
        / len(origins)
        for name in MODELS
    }


def run(database: Path, *, validation_end: str = "2022-12-31") -> dict:
    with sqlite3.connect(database) as connection:
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("SQLite integrity check failed")
        rows = connection.execute("SELECT day, price_usd FROM daily_price ORDER BY day").fetchall()
    if not rows or rows[0][0] != "2011-01-01":
        raise ValueError("Incomplete historical archive")
    days = [date.fromisoformat(day) for day, _ in rows]
    prices = [float(price) for _, price in rows]
    if any(not isfinite(price) or price <= 0 for price in prices):
        raise ValueError("Invalid price")
    if any(b - a != timedelta(days=1) for a, b in pairwise(days)):
        raise ValueError("Missing daily observation")
    cutoff = date.fromisoformat(validation_end)
    if cutoff >= days[-1]:
        raise ValueError("Validation cutoff leaves no locked test period")
    results = []
    for horizon in HORIZONS:
        _holdout, step = plan(horizon)
        # Non-overlapping targets in each split; never select on locked-test results.
        stride = max(step, horizon)
        first = max(365 + horizon + 365 - 1, 90)
        origins = range(first, len(days) - horizon, stride)
        validation = [
            i for i in origins if days[i + horizon] <= cutoff and days[i] >= date(2018, 1, 1)
        ]
        test = [i for i in origins if days[i] > cutoff]
        validation_scores = score(prices, validation, horizon)
        selected = min(MODELS, key=lambda name: (validation_scores[name], name))
        test_scores = score(prices, test, horizon)
        results.append(
            {
                "horizon_days": horizon,
                "selected_on_validation": selected,
                "validation_examples": len(validation),
                "locked_test_examples": len(test),
                "validation_mae_usd": validation_scores,
                "locked_test_mae_usd": test_scores,
                "selected_test_mae_usd": test_scores[selected],
                "persistence_test_mae_usd": test_scores["persistence"],
                "selected_test_improvement_vs_persistence_pct": (
                    100
                    * (test_scores["persistence"] - test_scores[selected])
                    / test_scores["persistence"]
                    if test_scores["persistence"]
                    else None
                ),
            }
        )
    return {
        "status": "MODEL_TOURNAMENT_RESEARCH_ONLY",
        "validation_end": validation_end,
        "models": list(MODELS),
        "results": results,
        "warning": (
            "Historical locked test is not prospective evidence; no automatic production promotion."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--validation-end", default="2022-12-31")
    args = parser.parse_args()
    result = run(args.database, validation_end=args.validation_end)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
