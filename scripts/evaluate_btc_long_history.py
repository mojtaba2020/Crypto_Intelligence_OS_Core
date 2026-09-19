#!/usr/bin/env python3
"""Evaluate a historical BTC PriceUSD research baseline without mixing Coinbase candles."""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import date, timedelta
from itertools import pairwise
from math import isfinite
from pathlib import Path

from crypto_intelligence_os.ai_forecasting import Observation, predict, train


def evaluate(database: Path, *, horizon: int, step: int, holdout_days: int) -> dict:
    if horizon < 1 or step < 1 or holdout_days < horizon + 1:
        raise ValueError("Invalid evaluation window")
    with sqlite3.connect(database) as connection:
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("SQLite integrity check failed")
        rows = connection.execute(
            "SELECT day, price_usd, source FROM daily_price ORDER BY day"
        ).fetchall()
        provenance = dict(connection.execute("SELECT key, value FROM provenance"))
    if not rows or len({row[2] for row in rows}) != 1:
        raise ValueError("Empty archive or mixed price sources")
    if rows[0][2] != "coinmetrics:btc:PriceUSD:1d":
        raise ValueError("Expected Coin Metrics PriceUSD research data only")
    observations = tuple(
        Observation(date.fromisoformat(day), float(price)) for day, price, _ in rows
    )
    if any(not isfinite(point.close) or point.close <= 0 for point in observations):
        raise ValueError("Invalid historical price")
    if observations[0].day != date(2011, 1, 1):
        raise ValueError("Historical series does not begin on 2011-01-01")
    for previous, current in pairwise(observations):
        if current.day - previous.day != timedelta(days=1):
            raise ValueError(f"Missing daily data between {previous.day} and {current.day}")
    last_origin = len(observations) - horizon - 1
    first_origin = max(14 + horizon + 30 - 1, len(observations) - holdout_days)
    origins = range(first_origin, last_origin + 1, step)
    errors = []
    for origin in origins:
        history = observations[: origin + 1]
        model = train(history, horizon_days=horizon)
        if model.last_training_target > history[-1].day:
            raise ValueError("Future label leakage")
        estimate = predict(model, history)
        actual = observations[origin + horizon].close
        baseline = history[-1].close
        errors.append((abs(estimate - actual), abs(baseline - actual),
                       100 * abs(estimate - actual) / actual,
                       100 * abs(baseline - actual) / actual))
    if not errors:
        raise ValueError("No resolved out-of-sample forecasts")
    n = len(errors)
    return {
        "status": "HISTORICAL_RESEARCH_EVALUATED",
        "metric": "Coin Metrics BTC PriceUSD daily aggregate; NOT Coinbase OHLCV",
        "license": provenance.get("license", "UNKNOWN"),
        "source_csv_sha256": provenance.get("source_csv_sha256"),
        "first_day": observations[0].day.isoformat(),
        "last_day": observations[-1].day.isoformat(),
        "horizon_days": horizon,
        "holdout_days": holdout_days,
        "evaluation_step_days": step,
        "test_examples": n,
        "first_test_origin": observations[first_origin].day.isoformat(),
        "last_test_origin": observations[first_origin + (n - 1) * step].day.isoformat(),
        "model_mae_usd": sum(e[0] for e in errors) / n,
        "persistence_mae_usd": sum(e[1] for e in errors) / n,
        "model_mape_pct": sum(e[2] for e in errors) / n,
        "persistence_mape_pct": sum(e[3] for e in errors) / n,
        "warning": (
            "Research only. Historical archive may be stale; "
            "no live forecast or profitability claim."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--horizon", type=int, default=7)
    parser.add_argument("--step", type=int, default=7)
    parser.add_argument("--holdout-days", type=int, default=365)
    args = parser.parse_args()
    result = evaluate(args.database, horizon=args.horizon, step=args.step,
                      holdout_days=args.holdout_days)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
