#!/usr/bin/env python3
"""First real point-in-time trained model tournament for hourly BTC closes."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

HORIZONS = (1, 2, 3, 4, 12)
LAGS = (1, 2, 3, 6, 12, 24, 48)


def _features(closes: list[float], origin: int) -> list[float]:
    current = closes[origin]
    feats = [1.0]
    for lag in LAGS:
        feats.append(math.log(current / closes[origin - lag]))
    returns = [math.log(closes[i] / closes[i - 1]) for i in range(origin - 23, origin + 1)]
    mean = sum(returns) / len(returns)
    variance = sum((x - mean) ** 2 for x in returns) / len(returns)
    feats.extend([mean, math.sqrt(variance)])
    return feats


def _solve(a: list[list[float]], b: list[float]) -> list[float]:
    n = len(b)
    aug = [[*row[:], b[i]] for i, row in enumerate(a)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(aug[r][col]))
        aug[col], aug[pivot] = aug[pivot], aug[col]
        scale = aug[col][col]
        if abs(scale) < 1e-12:
            raise ValueError("Singular training system")
        aug[col] = [x / scale for x in aug[col]]
        for row in range(n):
            if row == col:
                continue
            factor = aug[row][col]
            aug[row] = [x - factor * y for x, y in zip(aug[row], aug[col], strict=True)]
    return [aug[i][-1] for i in range(n)]


def _ridge_fit(xs: list[list[float]], ys: list[float], alpha: float) -> list[float]:
    p = len(xs[0])
    gram = [[0.0] * p for _ in range(p)]
    rhs = [0.0] * p
    for x, y in zip(xs, ys, strict=True):
        for i in range(p):
            rhs[i] += x[i] * y
            for j in range(p):
                gram[i][j] += x[i] * x[j]
    for i in range(1, p):
        gram[i][i] += alpha
    return _solve(gram, rhs)


def tournament(closes: list[float], train_min: int = 240, step: int = 24) -> dict:
    if len(closes) < train_min + 72 or any(p <= 0 for p in closes):
        raise ValueError("Need enough positive chronological hourly closes")
    rows = []
    for horizon in HORIZONS:
        ridge_err: list[float] = []
        base_err: list[float] = []
        direction_hits = 0
        samples = 0
        for test_origin in range(train_min, len(closes) - horizon, step):
            xs: list[list[float]] = []
            ys: list[float] = []
            for origin in range(48, test_origin - horizon + 1):
                xs.append(_features(closes, origin))
                ys.append(math.log(closes[origin + horizon] / closes[origin]))
            beta = _ridge_fit(xs, ys, alpha=1.0)
            x = _features(closes, test_origin)
            predicted_return = sum(w * v for w, v in zip(beta, x, strict=True))
            current = closes[test_origin]
            actual = closes[test_origin + horizon]
            predicted = current * math.exp(predicted_return)
            ridge_err.append(abs(predicted - actual) / actual)
            base_err.append(abs(current - actual) / actual)
            actual_return = math.log(actual / current)
            direction_hits += int((predicted_return >= 0) == (actual_return >= 0))
            samples += 1
        ridge_mape = 100 * sum(ridge_err) / samples
        base_mape = 100 * sum(base_err) / samples
        rows.append({
            "horizon_hours": horizon,
            "walk_forward_samples": samples,
            "ridge_mape_pct": round(ridge_mape, 5),
            "persistence_mape_pct": round(base_mape, 5),
            "ridge_direction_accuracy_pct": round(100 * direction_hits / samples, 2),
            "beats_persistence": ridge_mape < base_mape,
        })
    return {
        "status": "TRAINED_RIDGE_WALK_FORWARD_RESEARCH_V1",
        "target": "future_log_return",
        "features": "lagged_log_returns_plus_24h_mean_volatility",
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
