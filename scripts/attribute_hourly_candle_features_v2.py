#!/usr/bin/env python3
"""Walk-forward attribution of standardized hourly BTC candle features."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

try:
    from .ablate_hourly_features_v2 import _select, _standardize_train_test
    from .hourly_features_v2 import feature_names, feature_vector
    from .train_hourly_ridge_tournament import HORIZONS, _ridge_fit
except ImportError:  # pragma: no cover - direct script execution
    from ablate_hourly_features_v2 import _select, _standardize_train_test
    from hourly_features_v2 import feature_names, feature_vector
    from train_hourly_ridge_tournament import HORIZONS, _ridge_fit

CANDLE_INDICES = tuple(range(13, 18))


def _evaluate(
    candles: list[dict[str, float]],
    indices: tuple[int, ...],
    train_min: int,
    step: int,
    horizon: int,
    *,
    feature_cache: list[list[float] | None] | None = None,
    closes: list[float] | None = None,
) -> dict:
    if closes is None:
        closes = [float(c["close"]) for c in candles]
    if feature_cache is None:
        feature_cache = [
            feature_vector(candles, origin) if origin >= 168 else None
            for origin in range(len(candles))
        ]

    def cached_feature(origin: int) -> list[float]:
        row = feature_cache[origin]
        if row is None:
            raise ValueError(f"Feature cache missing origin {origin}")
        return row

    test_origins: list[int] = []
    errors: list[float] = []
    base_errors: list[float] = []
    hits = 0
    samples = 0
    for test_origin in range(train_min, len(candles) - horizon, step):
        origins = list(range(168, test_origin - horizon + 1))
        ys = [math.log(closes[o + horizon] / closes[o]) for o in origins]
        full_train = [cached_feature(o) for o in origins]
        full_test = cached_feature(test_origin)
        raw_train = [_select(row, indices) for row in full_train]
        raw_test = _select(full_test, indices)
        train_x, test_x = _standardize_train_test(raw_train, raw_test)
        train_x = [[1.0, *row] for row in train_x]
        test_x = [1.0, *test_x]
        beta = _ridge_fit(train_x, ys, alpha=1.0)

        current = closes[test_origin]
        actual = closes[test_origin + horizon]
        actual_return = math.log(actual / current)
        predicted_return = sum(weight * value for weight, value in zip(beta, test_x, strict=True))
        predicted = current * math.exp(predicted_return)
        test_origins.append(test_origin)
        errors.append(abs(predicted - actual) / actual)
        base_errors.append(abs(current - actual) / actual)
        hits += int((predicted_return >= 0) == (actual_return >= 0))
        samples += 1

    mape = 100 * sum(errors) / samples
    base_mape = 100 * sum(base_errors) / samples
    return {
        "feature_count": len(indices),
        "features": [feature_names()[i] for i in indices],
        "walk_forward_samples": samples,
        "mape_pct": round(mape, 5),
        "persistence_mape_pct": round(base_mape, 5),
        "mape_improvement_vs_persistence_pct": round(
            100 * (base_mape - mape) / base_mape,
            3,
        ),
        "direction_accuracy_pct": round(100 * hits / samples, 2),
        "beats_persistence": mape < base_mape,
        "paired_losses": {
            "origins": test_origins,
            "model_losses": errors,
            "baseline_losses": base_errors,
        },
    }


def tournament(candles: list[dict[str, float]], train_min: int = 360, step: int = 24) -> dict:
    closes = [float(c["close"]) for c in candles]
    feature_cache: list[list[float] | None] = [
        feature_vector(candles, origin) if origin >= 168 else None for origin in range(len(candles))
    ]
    rows = []
    for horizon in HORIZONS:
        single = {}
        leave_one_out = {}
        for index in CANDLE_INDICES:
            name = feature_names()[index]
            single[name] = _evaluate(
                candles,
                (index,),
                train_min,
                step,
                horizon,
                feature_cache=feature_cache,
                closes=closes,
            )
            remaining = tuple(i for i in CANDLE_INDICES if i != index)
            leave_one_out[f"without_{name}"] = _evaluate(
                candles,
                remaining,
                train_min,
                step,
                horizon,
                feature_cache=feature_cache,
                closes=closes,
            )
        full = _evaluate(
            candles,
            CANDLE_INDICES,
            train_min,
            step,
            horizon,
            feature_cache=feature_cache,
            closes=closes,
        )
        rows.append(
            {
                "horizon_hours": horizon,
                "full_candle_family": full,
                "single_feature": single,
                "leave_one_out": leave_one_out,
            }
        )
    return {
        "status": "CANDLE_FEATURE_ATTRIBUTION_STANDARDIZED_V1",
        "model": "ridge_alpha_1",
        "scaling": "training_only_zscore_per_walk_forward_split",
        "target": "future_log_return",
        "method": ["single_feature", "leave_one_out"],
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
