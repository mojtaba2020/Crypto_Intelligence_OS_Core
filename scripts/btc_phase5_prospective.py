#!/usr/bin/env python3
"""Phase 5 prospective BTC forecast ledger: issue forecasts before outcomes exist.

The ledger is append-only. The caller must preserve it between invocations.
Only completed UTC daily closes are eligible; the evaluation command never
re-trains, replaces, or backfills a forecast.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import UTC, date, datetime, timedelta
from itertools import pairwise
from math import isfinite
from pathlib import Path

from crypto_intelligence_os.ai_forecasting import Observation
from crypto_intelligence_os.hybrid_forecasting import predict_hybrid, train_hybrid

HORIZONS = (7, 30)
VERSION = "phase5-hybrid-all-ridge100-v1"


def read_prices(database: Path) -> tuple[Observation, ...]:
    with sqlite3.connect(database) as connection:
        rows = connection.execute("SELECT day, price_usd FROM daily_price ORDER BY day").fetchall()
    history = tuple(Observation(date.fromisoformat(day), float(price)) for day, price in rows)
    if not history or any(not isfinite(p.close) or p.close <= 0 for p in history):
        raise ValueError("Invalid price archive")
    if any((b.day - a.day).days != 1 for a, b in pairwise(history)):
        raise ValueError("Missing daily price")
    return history


def load_ledger(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def issue(
    database: Path, ledger: Path, *, now: datetime, horizons: tuple[int, ...] = HORIZONS
) -> list[dict]:
    if now.tzinfo is None:
        raise ValueError("UTC-aware issuance time required")
    now = now.astimezone(UTC)
    history = read_prices(database)
    origin = history[-1]
    if origin.day >= now.date():
        raise ValueError("Forecast origin must be a completed UTC day")
    if origin.day < now.date() - timedelta(days=2):
        raise ValueError("Price archive is stale")
    existing = load_ledger(ledger)
    keys = {(row["version"], row["origin_day"], row["horizon_days"]) for row in existing}
    created = []
    for horizon in horizons:
        key = (VERSION, origin.day.isoformat(), horizon)
        if key in keys:
            continue
        model = train_hybrid(history, horizon_days=horizon)
        if model.last_training_target > origin.day:
            raise ValueError("Future-label leakage")
        created.append(
            {
                "version": VERSION,
                "issued_at_utc": now.isoformat(),
                "origin_day": origin.day.isoformat(),
                "target_day": (origin.day + timedelta(days=horizon)).isoformat(),
                "horizon_days": horizon,
                "origin_close_usd": origin.close,
                "hybrid_forecast_usd": predict_hybrid(model, history),
                "persistence_forecast_usd": origin.close,
                "training_examples": model.train_examples,
                "last_training_target": model.last_training_target.isoformat(),
                "research_only": True,
            }
        )
    if created:
        ledger.parent.mkdir(parents=True, exist_ok=True)
        with ledger.open("a", encoding="utf-8") as output:
            for row in created:
                output.write(json.dumps(row, sort_keys=True) + "\n")
    return created


def score(database: Path, ledger: Path, *, now: datetime) -> dict:
    if now.tzinfo is None:
        raise ValueError("UTC-aware scoring time required")
    today = now.astimezone(UTC).date()
    closes = {point.day.isoformat(): point.close for point in read_prices(database)}
    rows = load_ledger(ledger)
    results = {}
    for horizon in HORIZONS:
        eligible = [
            row
            for row in rows
            if row["version"] == VERSION
            and row["horizon_days"] == horizon
            and date.fromisoformat(row["target_day"]) < today
            and datetime.fromisoformat(row["issued_at_utc"]).astimezone(UTC).date()
            <= date.fromisoformat(row["origin_day"]) + timedelta(days=1)
            and datetime.fromisoformat(row["issued_at_utc"]).astimezone(UTC).date()
            < date.fromisoformat(row["target_day"])
            and row["target_day"] in closes
        ]
        paired = [
            (
                abs(row["hybrid_forecast_usd"] - closes[row["target_day"]]),
                abs(row["persistence_forecast_usd"] - closes[row["target_day"]]),
            )
            for row in eligible
        ]
        results[str(horizon)] = {
            "resolved_examples": len(paired),
            "hybrid_mae_usd": sum(a for a, _ in paired) / len(paired) if paired else None,
            "persistence_mae_usd": sum(b for _, b in paired) / len(paired) if paired else None,
            "hybrid_lower_error_count": sum(a < b for a, b in paired),
            "hybrid_higher_error_count": sum(a > b for a, b in paired),
        }
    return {
        "status": "PROSPECTIVE_EVALUATION_IN_PROGRESS",
        "model_version": VERSION,
        "ledger_entries": len(rows),
        "by_horizon": results,
        "research_only": True,
        "limitations": (
            "Only forecasts issued before their target close count; no profitability claim."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--mode", choices=("issue", "score"), required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    now = datetime.now(UTC)
    result = (
        issue(args.database, args.ledger, now=now)
        if args.mode == "issue"
        else score(args.database, args.ledger, now=now)
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
