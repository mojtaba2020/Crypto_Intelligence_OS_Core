#!/usr/bin/env python3
"""Walk-forward ablation of point-in-time-safe hourly BTC feature families."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path

try:
    from .hourly_features_v2 import feature_names, feature_vector
    from .train_hourly_ridge_tournament import HORIZONS, _ridge_fit
except ImportError:  # pragma: no cover - direct script execution
    from hourly_features_v2 import feature_names, feature_vector
    from train_hourly_ridge_tournament import HORIZONS, _ridge_fit

FAMILIES = {
    "returns": tuple(range(0, 9)),
    "volatility": tuple(range(9, 13)),
    "candle": tuple(range(13, 18)),
    "volume": tuple(range(18, 22)),
    "all_v2": tuple(range(22)),
}


def _standardize_train_test(
    train: list[list[float]], test: list[float]
) -> tuple[list[list[float]], list[float]]:
    means = [statistics.mean(row[j] for row in train) for j in range(len(test))]
    stds = [statistics.pstdev(row[j] for row in train) for j in range(len(test))]
    scaled_train = [
        [(value - means[j]) / stds[j] if stds[j] else 0.0 for j, value in enumerate(row)]
        for row in train
    ]
    scaled_test = [(value - means[j]) / stds[j] if stds[j] else 0.0 for j, value in enumerate(test)]
    return scaled_train, scaled_test


def _select(vector: list[float], indices: tuple[int, ...]) -> list[float]:
    return [vector[i] for i in indices]


def tournament(candles: list[dict[str, float]], train_min: int = 360, step: int = 24) -> dict:
    closes = [float(c["close"]) for c in candles]
    rows = []
    for horizon in HORIZONS:
        errors = {name: [] for name in FAMILIES}
        hits = {name: 0 for name in FAMILIES}
        base_errors: list[float] = []
        samples = 0
        for test_origin in range(train_min, len(candles) - horizon, step):
            origins = list(range(168, test_origin - horizon + 1))
            ys = [math.log(closes[o + horizon] / closes[o]) for o in origins]
            full_train = [feature_vector(candles, o) for o in origins]
            full_test = feature_vector(candles, test_origin)
            current = closes[test_origin]
            actual = closes[test_origin + horizon]
            actual_return = math.log(actual / current)
            base_errors.append(abs(current - actual) / actual)

            for name, indices in FAMILIES.items():
                raw_train = [_select(row, indices) for row in full_train]
                raw_test = _select(full_test, indices)
                train_x, test_x = _standardize_train_test(raw_train, raw_test)
                train_x = [[1.0, *row] for row in train_x]
                test_x = [1.0, *test_x]
                beta = _ridge_fit(train_x, ys, alpha=1.0)
                predicted_return = sum(
                    weight * value for weight, value in zip(beta, test_x, strict=True)
                )
                predicted = current * math.exp(predicted_return)
                errors[name].append(abs(predicted - actual) / actual)
                hits[name] += int((predicted_return >= 0) == (actual_return >= 0))
            samples += 1

        base_mape = 100 * sum(base_errors) / samples
        family_results = {}
        for name, indices in FAMILIES.items():
            mape = 100 * sum(errors[name]) / samples
            family_results[name] = {
                "feature_count": len(indices),
                "features": [feature_names()[i] for i in indices],
                "mape_pct": round(mape, 5),
                "direction_accuracy_pct": round(100 * hits[name] / samples, 2),
                "beats_persistence": mape < base_mape,
            }
        rows.append(
            {
                "horizon_hours": horizon,
                "walk_forward_samples": samples,
                "persistence_mape_pct": round(base_mape, 5),
                "families": family_results,
            }
        )
    return {
        "status": "FEATURE_V2_FAMILY_ABLATION_STANDARDIZED_V1",
        "model": "ridge_alpha_1",
        "scaling": "training_only_zscore_per_walk_forward_split",
        "target": "future_log_return",
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    candles = json.loads(args.input.read_text(encoding="utf-8"))
    report = tournament(candles)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
