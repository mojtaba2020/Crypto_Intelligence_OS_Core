#!/usr/bin/env python3
"""Second BTC intern: nonlinear Extra Trees walk-forward tournament."""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

HORIZONS = (1, 2, 3, 4, 12)
LAGS = (1, 2, 3, 6, 12, 24, 48)


def _features(closes: list[float], origin: int) -> list[float]:
    current = closes[origin]
    feats = [math.log(current / closes[origin - lag]) for lag in LAGS]
    returns = [math.log(closes[i] / closes[i - 1]) for i in range(origin - 23, origin + 1)]
    mean = sum(returns) / len(returns)
    variance = sum((x - mean) ** 2 for x in returns) / len(returns)
    feats.extend([mean, math.sqrt(variance)])
    return feats


def _tree_predict(
    xs: list[list[float]], ys: list[float], x: list[float], rng: random.Random, depth: int = 0
) -> float:
    if depth >= 6 or len(ys) < 24:
        return sum(ys) / len(ys)
    feature = rng.randrange(len(x))
    values = [row[feature] for row in xs]
    lo, hi = min(values), max(values)
    if lo == hi:
        return sum(ys) / len(ys)
    threshold = rng.uniform(lo, hi)
    left = [i for i, row in enumerate(xs) if row[feature] <= threshold]
    right = [i for i, row in enumerate(xs) if row[feature] > threshold]
    if len(left) < 8 or len(right) < 8:
        return sum(ys) / len(ys)
    indices = left if x[feature] <= threshold else right
    return _tree_predict([xs[i] for i in indices], [ys[i] for i in indices], x, rng, depth + 1)


def _forest_predict(xs: list[list[float]], ys: list[float], x: list[float], seed: int) -> float:
    predictions = []
    for tree in range(64):
        rng = random.Random(seed + tree)
        predictions.append(_tree_predict(xs, ys, x, rng))
    return sum(predictions) / len(predictions)


def tournament(closes: list[float], train_min: int = 240, step: int = 24) -> dict:
    if len(closes) < train_min + 72 or any(p <= 0 for p in closes):
        raise ValueError("Need enough positive chronological hourly closes")
    rows = []
    for horizon in HORIZONS:
        model_err, base_err = [], []
        direction_hits = samples = 0
        for test_origin in range(train_min, len(closes) - horizon, step):
            xs, ys = [], []
            for origin in range(48, test_origin - horizon + 1):
                xs.append(_features(closes, origin))
                ys.append(math.log(closes[origin + horizon] / closes[origin]))
            x = _features(closes, test_origin)
            predicted_return = _forest_predict(xs, ys, x, seed=10_000 * horizon + test_origin)
            current, actual = closes[test_origin], closes[test_origin + horizon]
            predicted = current * math.exp(predicted_return)
            model_err.append(abs(predicted - actual) / actual)
            base_err.append(abs(current - actual) / actual)
            actual_return = math.log(actual / current)
            direction_hits += int((predicted_return >= 0) == (actual_return >= 0))
            samples += 1
        model_mape = 100 * sum(model_err) / samples
        base_mape = 100 * sum(base_err) / samples
        rows.append({
            "horizon_hours": horizon,
            "walk_forward_samples": samples,
            "extra_trees_mape_pct": round(model_mape, 5),
            "persistence_mape_pct": round(base_mape, 5),
            "extra_trees_direction_accuracy_pct": round(100 * direction_hits / samples, 2),
            "beats_persistence": model_mape < base_mape,
        })
    return {"status": "TRAINED_EXTRA_TREES_WALK_FORWARD_RESEARCH_V1",
            "target": "future_log_return",
            "features": "lagged_log_returns_plus_24h_mean_volatility",
            "rows": rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    closes = json.loads(args.input.read_text(encoding="utf-8"))
    report = tournament([float(x) for x in closes])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
