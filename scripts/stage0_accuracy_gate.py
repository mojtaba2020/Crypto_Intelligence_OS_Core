#!/usr/bin/env python3
"""Auditable, leakage-aware walk-forward benchmark for hourly BTC close forecasts.

Run with: python scripts/stage0_accuracy_gate.py --candles path/to/hourly.json
Input: JSON list of [ISO-8601 UTC timestamp, close] pairs, ordered or unordered.
Research only: no automatic model promotion or trading decisions.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from datetime import datetime, timedelta
from itertools import pairwise
from pathlib import Path

from crypto_intelligence_os.hybrid_forecasting import _estimate, _fit

HORIZONS = (1, 4, 12, 24)
WINDOWS = (1, 4, 12, 24, 72, 168)
RIDGES = (1.0, 10.0, 100.0)
MIN_TRAIN = 400
VALIDATION = 96
TEST = 96


def load_candles(path: Path):
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = sorted((datetime.fromisoformat(t.replace("Z", "+00:00")), float(p)) for t, p in raw)
    if len(rows) < 168 + MIN_TRAIN + VALIDATION + TEST + max(HORIZONS):
        raise ValueError("Not enough candles for a purged train/validation/test split")
    if any(
        t.tzinfo is None or t.utcoffset() != timedelta(0) or not math.isfinite(p) or p <= 0
        for t, p in rows
    ):
        raise ValueError("Timestamps must be UTC and close prices finite and positive")
    if any(b[0] - a[0] != timedelta(hours=1) for a, b in pairwise(rows)):
        raise ValueError("Missing or duplicate hourly candle")
    return rows


def features(prices, i):
    values = [math.log(prices[i] / prices[i - w]) for w in WINDOWS]
    one_hour = [math.log(prices[j] / prices[j - 1]) for j in range(i - 23, i + 1)]
    return (*values, statistics.pstdev(one_hour))


def mae(predictions, actuals):
    return statistics.mean(abs(p - y) for p, y in zip(predictions, actuals, strict=True))


def evaluate(rows, horizon):
    prices = [p for _, p in rows]
    last_origin = len(prices) - 1 - horizon
    first_test = last_origin - TEST + 1
    first_validation = first_test - VALIDATION
    # Training labels must resolve BEFORE validation starts. Validation labels
    # must resolve BEFORE the untouched test starts.
    train_origins = range(168, first_validation - horizon)
    validation_origins = range(first_validation, first_test - horizon)
    test_origins = range(first_test, last_origin + 1)
    if len(train_origins) < MIN_TRAIN or len(validation_origins) < 48:
        raise ValueError("Insufficient resolved, purged samples")

    def examples(origins):
        return [(features(prices, i), math.log(prices[i + horizon] / prices[i])) for i in origins]

    training = examples(train_origins)
    validation = examples(validation_origins)
    candidates = {"persistence": (0.0, None)}
    for ridge in RIDGES:
        fitted = _fit(training, ridge=ridge)
        for blend in (0.25, 0.5, 1.0):
            candidates[f"ridge_{ridge:g}_blend_{blend:g}"] = (blend, fitted)
    validation_scores = {}
    for name, (blend, fitted) in candidates.items():
        predictions = [
            0.0 if fitted is None else blend * _estimate(*fitted, x) for x, _ in validation
        ]
        validation_scores[name] = mae(predictions, [y for _, y in validation])
    winner = min(
        validation_scores,
        key=lambda name: (validation_scores[name], name != "persistence"),
    )
    # Refit only on labels resolved before first test origin; no test labels used.
    final_training = examples(range(168, first_test - horizon))
    blend, fitted = candidates[winner]
    if fitted is not None:
        ridge = float(winner.split("_")[1])
        fitted = _fit(final_training, ridge=ridge)
    origins = list(test_origins)
    actual_returns = [math.log(prices[i + horizon] / prices[i]) for i in origins]
    predicted_returns = [
        0.0 if fitted is None else blend * _estimate(*fitted, features(prices, i)) for i in origins
    ]
    actual_prices = [prices[i + horizon] for i in origins]
    model_prices = [
        prices[i] * math.exp(max(-0.2, min(0.2, r)))
        for i, r in zip(origins, predicted_returns, strict=True)
    ]
    baseline_prices = [prices[i] for i in origins]
    model_mae = mae(model_prices, actual_prices)
    baseline_mae = mae(baseline_prices, actual_prices)
    return {
        "horizon_hours": horizon,
        "candidate_selected_on_validation": winner,
        "train_examples": len(final_training),
        "validation_examples": len(validation),
        "test_examples": len(origins),
        "test_start_utc": rows[first_test][0].isoformat(),
        "test_end_utc": rows[last_origin + horizon][0].isoformat(),
        "test_model_mae_usd": model_mae,
        "test_persistence_mae_usd": baseline_mae,
        "test_mae_improvement_pct": (
            100 * (baseline_mae - model_mae) / baseline_mae if baseline_mae else None
        ),
        "test_model_return_mae": mae(predicted_returns, actual_returns),
        "test_persistence_return_mae": mae([0.0] * len(origins), actual_returns),
        "eligible_for_promotion": bool(model_mae < baseline_mae and winner != "persistence"),
        "warning": (
            "One held-out block is not proof of persistent skill; "
            "use multiple forward periods and prospective scoring."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candles", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    rows = load_candles(args.candles)
    report = {
        "status": "RESEARCH_ONLY",
        "source": str(args.candles),
        "results": [evaluate(rows, h) for h in HORIZONS],
    }
    output = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output, encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
