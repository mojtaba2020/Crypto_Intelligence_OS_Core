#!/usr/bin/env python3
"""Generate point-in-time hourly losses for Champion/Challenger judging."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from hourly_champion_challenger import BENCHMARK, CANDIDATES, HORIZONS
from train_hourly_boosting_tournament import _boost_predict
from train_hourly_boosting_tournament import (
    _features as _boosting_features,
)
from train_hourly_extra_trees_tournament import (
    _features as _extra_trees_features,
)
from train_hourly_extra_trees_tournament import _forest_predict
from train_hourly_ridge_tournament import _features as _ridge_features
from train_hourly_ridge_tournament import _ridge_fit

TRAIN_MIN = 240
STEP = 24
VALIDATION_FRACTION = 0.5


def _predict(model: str, closes: list[float], origin: int, horizon: int) -> float:
    feature_fn = {
        "ridge": _ridge_features,
        "extra_trees": _extra_trees_features,
        "boosting": _boosting_features,
    }.get(model)
    if feature_fn is None:
        raise ValueError(f"Unknown model: {model}")

    xs: list[list[float]] = []
    ys: list[float] = []
    for train_origin in range(48, origin - horizon + 1):
        xs.append(feature_fn(closes, train_origin))
        ys.append(math.log(closes[train_origin + horizon] / closes[train_origin]))
    x = feature_fn(closes, origin)
    if model == "ridge":
        beta = _ridge_fit(xs, ys, alpha=1.0)
        return sum(weight * value for weight, value in zip(beta, x, strict=True))
    if model == "extra_trees":
        return _forest_predict(xs, ys, x, seed=10_000 * horizon + origin)
    if model == "boosting":
        return _boost_predict(xs, ys, x)
    raise ValueError(f"Unknown model: {model}")


def generate(closes: list[float]) -> dict:
    if len(closes) < 1000 or any(not math.isfinite(x) or x <= 0 for x in closes):
        raise ValueError("Need at least 1000 positive finite chronological hourly closes")

    origins = list(range(TRAIN_MIN, len(closes) - max(HORIZONS), STEP))
    if len(origins) < 80:
        raise ValueError("Need at least 80 resolved walk-forward origins")
    split_index = int(len(origins) * VALIDATION_FRACTION)
    validation_origins = origins[:split_index]
    locked_origins = origins[split_index:]
    if len(validation_origins) < 40 or len(locked_origins) < 40:
        raise ValueError("Validation and locked test each require at least 40 origins")

    rows = []
    for horizon in HORIZONS:
        for origin in origins:
            actual = closes[origin + horizon]
            current = closes[origin]
            losses = {BENCHMARK: abs(current - actual) / actual}
            for model in CANDIDATES:
                predicted_return = _predict(model, closes, origin, horizon)
                predicted = current * math.exp(predicted_return)
                losses[model] = abs(predicted - actual) / actual
            rows.append(
                {
                    "horizon_hours": horizon,
                    "origin": origin,
                    "split": (
                        "validation" if origin in validation_origins else "locked_test"
                    ),
                    "losses": losses,
                }
            )

    return {
        "status": "HOURLY_POINT_IN_TIME_LOSSES_V1",
        "horizons_hours": list(HORIZONS),
        "candidates": list(CANDIDATES),
        "benchmark": BENCHMARK,
        "train_min_hours": TRAIN_MIN,
        "walk_forward_step_hours": STEP,
        "validation_end_origin": validation_origins[-1],
        "locked_test_start_origin": locked_origins[0],
        "validation_origins": len(validation_origins),
        "locked_test_origins": len(locked_origins),
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    closes = [float(x) for x in json.loads(args.input.read_text(encoding="utf-8"))]
    report = generate(closes)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {key: value for key, value in report.items() if key != "rows"},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
