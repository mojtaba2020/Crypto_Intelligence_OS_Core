#!/usr/bin/env python3
"""Third BTC intern: gradient-boosted regression trees walk-forward tournament."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

HORIZONS = (1, 2, 3, 4, 12)
LAGS = (1, 2, 3, 6, 12, 24, 48)
N_ESTIMATORS = 32
LEARNING_RATE = 0.05
MAX_DEPTH = 2
MIN_LEAF = 12


def _features(closes: list[float], origin: int) -> list[float]:
    current = closes[origin]
    feats = [math.log(current / closes[origin - lag]) for lag in LAGS]
    returns = [math.log(closes[i] / closes[i - 1]) for i in range(origin - 23, origin + 1)]
    mean = sum(returns) / len(returns)
    variance = sum((x - mean) ** 2 for x in returns) / len(returns)
    feats.extend([mean, math.sqrt(variance)])
    return feats


def _leaf(value: float) -> tuple[str, float]:
    return ("leaf", value)


def _fit_tree(
    xs: list[list[float]], ys: list[float], indices: list[int], depth: int = 0
) -> tuple:
    mean = sum(ys[i] for i in indices) / len(indices)
    if depth >= MAX_DEPTH or len(indices) < 2 * MIN_LEAF:
        return _leaf(mean)

    best: tuple[float, int, float, list[int], list[int]] | None = None
    for feature in range(len(xs[0])):
        ordered = sorted(indices, key=lambda i: xs[i][feature])
        prefix_sum = 0.0
        prefix_sq = 0.0
        total_sum = sum(ys[i] for i in ordered)
        total_sq = sum(ys[i] * ys[i] for i in ordered)
        for pos in range(1, len(ordered)):
            value = ys[ordered[pos - 1]]
            prefix_sum += value
            prefix_sq += value * value
            if pos < MIN_LEAF or len(ordered) - pos < MIN_LEAF:
                continue
            left_x = xs[ordered[pos - 1]][feature]
            right_x = xs[ordered[pos]][feature]
            if left_x == right_x:
                continue
            right_sum = total_sum - prefix_sum
            right_sq = total_sq - prefix_sq
            left_sse = prefix_sq - prefix_sum * prefix_sum / pos
            right_n = len(ordered) - pos
            right_sse = right_sq - right_sum * right_sum / right_n
            loss = left_sse + right_sse
            threshold = (left_x + right_x) / 2
            if best is None or loss < best[0]:
                best = (loss, feature, threshold, ordered[:pos], ordered[pos:])

    if best is None:
        return _leaf(mean)
    _, feature, threshold, left, right = best
    return (
        "node",
        feature,
        threshold,
        _fit_tree(xs, ys, left, depth + 1),
        _fit_tree(xs, ys, right, depth + 1),
    )


def _predict_tree(tree: tuple, x: list[float]) -> float:
    if tree[0] == "leaf":
        return float(tree[1])
    _, feature, threshold, left, right = tree
    return _predict_tree(left if x[feature] <= threshold else right, x)


def _boost_predict(xs: list[list[float]], ys: list[float], x: list[float]) -> float:
    base = sum(ys) / len(ys)
    train_pred = [base] * len(ys)
    prediction = base
    indices = list(range(len(ys)))
    for _ in range(N_ESTIMATORS):
        residuals = [y - pred for y, pred in zip(ys, train_pred, strict=True)]
        tree = _fit_tree(xs, residuals, indices)
        updates = [_predict_tree(tree, row) for row in xs]
        train_pred = [
            pred + LEARNING_RATE * update
            for pred, update in zip(train_pred, updates, strict=True)
        ]
        prediction += LEARNING_RATE * _predict_tree(tree, x)
    return prediction


def tournament(closes: list[float], train_min: int = 240, step: int = 24) -> dict:
    if len(closes) < train_min + 72 or any(p <= 0 for p in closes):
        raise ValueError("Need enough positive chronological hourly closes")
    rows = []
    for horizon in HORIZONS:
        model_err: list[float] = []
        base_err: list[float] = []
        direction_hits = 0
        samples = 0
        for test_origin in range(train_min, len(closes) - horizon, step):
            xs: list[list[float]] = []
            ys: list[float] = []
            for origin in range(48, test_origin - horizon + 1):
                xs.append(_features(closes, origin))
                ys.append(math.log(closes[origin + horizon] / closes[origin]))
            x = _features(closes, test_origin)
            predicted_return = _boost_predict(xs, ys, x)
            current = closes[test_origin]
            actual = closes[test_origin + horizon]
            predicted = current * math.exp(predicted_return)
            model_err.append(abs(predicted - actual) / actual)
            base_err.append(abs(current - actual) / actual)
            actual_return = math.log(actual / current)
            direction_hits += int((predicted_return >= 0) == (actual_return >= 0))
            samples += 1
        model_mape = 100 * sum(model_err) / samples
        base_mape = 100 * sum(base_err) / samples
        rows.append(
            {
                "horizon_hours": horizon,
                "walk_forward_samples": samples,
                "boosting_mape_pct": round(model_mape, 5),
                "persistence_mape_pct": round(base_mape, 5),
                "boosting_direction_accuracy_pct": round(100 * direction_hits / samples, 2),
                "beats_persistence": model_mape < base_mape,
            }
        )
    return {
        "status": "TRAINED_GRADIENT_BOOSTING_WALK_FORWARD_RESEARCH_V1",
        "target": "future_log_return",
        "features": "lagged_log_returns_plus_24h_mean_volatility",
        "n_estimators": N_ESTIMATORS,
        "learning_rate": LEARNING_RATE,
        "max_depth": MAX_DEPTH,
        "rows": rows,
    }


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
