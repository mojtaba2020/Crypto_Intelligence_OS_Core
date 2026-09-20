#!/usr/bin/env python3
"""Paired past-only BTC volume ablation using one Coinbase OHLCV source."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import date, timedelta
from math import exp, isfinite, log
from pathlib import Path

from crypto_intelligence_os.ai_forecasting import Observation
from crypto_intelligence_os.hybrid_forecasting import _estimate, _fit, features


def evaluate(database: Path, *, horizon: int, step: int) -> dict:
    if horizon < 1 or step < 1:
        raise ValueError("Positive horizon and step required")
    with sqlite3.connect(database) as connection:
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Corrupt OHLCV database")
        rows = connection.execute(
            "SELECT day, close, volume_btc FROM coinbase_ohlcv ORDER BY day"
        ).fetchall()
    if not rows:
        raise ValueError("No OHLCV observations")
    observations = tuple(
        Observation(date.fromisoformat(day), float(close)) for day, close, _ in rows
    )
    volumes = tuple(float(volume) for _, _, volume in rows)
    for index, point in enumerate(observations):
        if (
            not isfinite(point.close)
            or point.close <= 0
            or not isfinite(volumes[index])
            or volumes[index] < 0
        ):
            raise ValueError("Invalid OHLCV value")
        if index and point.day - observations[index - 1].day != timedelta(days=1):
            raise ValueError("OHLCV history must be contiguous")
    if len(rows) < 365 + horizon + 365 + horizon + 1:
        raise ValueError("Insufficient volume history for past-only training and holdout")

    def volume_features(index: int) -> tuple[float, ...]:
        current = sum(volumes[index - 6 : index + 1]) / 7
        previous = sum(volumes[index - 29 : index - 6]) / 23
        return (log((current + 1) / (previous + 1)), log(1 + current))

    errors: list[tuple[float, float, float]] = []
    origins: list[str] = []
    first = 365 + horizon + 365
    for origin in range(first, len(rows) - horizon, step):
        # Every training target resolves no later than this forecast origin.
        train_indices = range(365, origin - horizon + 1)
        plain = [
            (features(observations, index, group="momentum_only"),
             log(observations[index + horizon].close / observations[index].close))
            for index in train_indices
        ]
        augmented = [
            (values + volume_features(index), target)
            for index, (values, target) in zip(train_indices, plain, strict=True)
        ]
        plain_fit = _fit(plain, ridge=100.0)
        volume_fit = _fit(augmented, ridge=100.0)
        signal_plain = _estimate(*plain_fit, features(observations, origin, group="momentum_only"))
        signal_volume = _estimate(
            *volume_fit,
            features(observations, origin, group="momentum_only") + volume_features(origin),
        )
        current = observations[origin].close
        actual = observations[origin + horizon].close
        errors.append((
            abs(current * exp(max(-1.0, min(1.0, signal_plain))) - actual),
            abs(current * exp(max(-1.0, min(1.0, signal_volume))) - actual),
            abs(current - actual),
        ))
        origins.append(observations[origin].day.isoformat())
    if not errors:
        raise ValueError("No resolved out-of-sample origins")
    n = len(errors)
    return {
        "status": "PAIRED_COINBASE_VOLUME_ABLATION",
        "source": "Coinbase BTC-USD daily OHLCV; price and volume from the same candles",
        "first_data_day": rows[0][0],
        "last_data_day": rows[-1][0],
        "first_test_origin": origins[0],
        "last_test_origin": origins[-1],
        "horizon_days": horizon,
        "step_days": step,
        "test_examples": n,
        "mae_usd": {
            "price_only": sum(row[0] for row in errors) / n,
            "price_plus_volume": sum(row[1] for row in errors) / n,
            "persistence": sum(row[2] for row in errors) / n,
        },
        "volume_lower_error_count": sum(row[1] < row[0] for row in errors),
        "volume_higher_error_count": sum(row[1] > row[0] for row in errors),
        "volume_equal_error_count": sum(row[1] == row[0] for row in errors),
        "mean_paired_volume_minus_price_error_usd": sum(row[1] - row[0] for row in errors) / n,
        "research_only": True,
        "limitations": (
            "Coinbase-only era; no volume is imputed before archive start. "
            "Same origins, same resolved labels and same ridge regularization; "
            "no claim of profitable forecasting."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--horizon", type=int, required=True)
    parser.add_argument("--step", type=int, required=True)
    args = parser.parse_args()
    result = evaluate(args.database, horizon=args.horizon, step=args.step)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
