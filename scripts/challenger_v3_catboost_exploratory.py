#!/usr/bin/env python3
"""Opt-in, development-only CatBoost research outside the frozen V3 family.

This is NOT evidence of statistical significance, champion status or permission
for a locked-OOS read. Only pre-extracted development/validation slices are allowed.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import statistics
from pathlib import Path
from typing import Any

try:
    from scripts.multitimeframe_features_v3 import (
        WINDOWS,
        _next_period_timestamp,
        feature_vector,
        is_temporally_valid_sample,
    )
except ModuleNotFoundError:  # direct execution from scripts/
    from multitimeframe_features_v3 import (
        WINDOWS,
        _next_period_timestamp,
        feature_vector,
        is_temporally_valid_sample,
    )

SCOPE = "development_validation_only"
SEED = 20261012
MAX_FOLDS = 12
MAX_TRAIN_ROWS = 256
MIN_TRAIN_ROWS = 40
FORBIDDEN_PATH_PARTS = ("locked", "oos", "production", "fresh")


def _safe_path(path: Path, *, suffix: str) -> Path:
    if not path.name.endswith(suffix):
        raise ValueError(f"Path must end in {suffix}")
    if any(word in part.lower() for part in path.parts for word in FORBIDDEN_PATH_PARTS):
        raise ValueError("Reserved/locked/production paths are forbidden in the exploratory lane")
    if path.is_symlink():
        raise ValueError("Symlink paths are not accepted")
    return path


def _validate_candles(candles: list[dict[str, Any]], family: str) -> None:
    if family not in WINDOWS:
        raise ValueError("Unsupported time family")
    if len(candles) <= max(WINDOWS[family]) + MIN_TRAIN_ROWS + 1:
        raise ValueError("Insufficient development-only candles")
    last_timestamp: int | None = None
    for row in candles:
        if row.get("is_complete") is not True:
            raise ValueError("Incomplete candles forbidden: never interpolate or backfill")
        stamp = row.get("timestamp")
        if isinstance(stamp, bool) or not isinstance(stamp, (int, float)):
            raise ValueError("Every candle requires an integer timestamp")
        if not math.isfinite(stamp) or int(stamp) != stamp:
            raise ValueError("Invalid timestamp")
        timestamp = int(stamp)
        if last_timestamp is not None and timestamp != _next_period_timestamp(
            last_timestamp, family
        ):
            raise ValueError("Noncontiguous candle calendar: no interpolation allowed")
        last_timestamp = timestamp
        for name in ("open", "high", "low", "close", "volume"):
            value = row.get(name)
            if isinstance(value, bool) or not isinstance(value, (float, int)):
                raise ValueError(f"Invalid candle {name}")
            if not math.isfinite(value):
                raise ValueError(f"Nonfinite candle {name}")
        opening, high, low, close = (float(row[k]) for k in ("open", "high", "low", "close"))
        if low <= 0 or min(opening, close) <= 0 or high < max(opening, close) or low > min(
            opening, close
        ) or float(row["volume"]) < 0:
            raise ValueError("Invalid OHLCV bounds")


def load_development_slice(path: Path) -> tuple[list[dict[str, Any]], str]:
    """Only an operator-curated development slice; never a full/locked artifact.

    Scope metadata is an assertion, not independent provenance verification.
    Source-boundary evidence must be reviewed by a human before use.
    """
    path = _safe_path(path, suffix=".development.json")
    if path.stat().st_size > 10_000_000:
        raise ValueError("Development input exceeds the fixed 10MB limit")
    payload = json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")),
    )
    if not isinstance(payload, dict) or set(payload) != {"scope", "source", "candles"}:
        raise ValueError("Expected closed-schema development-slice payload")
    if payload["scope"] != SCOPE:
        raise ValueError("Fresh Locked OOS or other non-development scope is forbidden")
    if not isinstance(payload["source"], str) or not payload["source"].strip():
        raise ValueError("Development source identity is required")
    if not isinstance(payload["candles"], list) or not all(
        isinstance(item, dict) for item in payload["candles"]
    ):
        raise ValueError("Development candles must be a list of objects")
    return payload["candles"], payload["source"]


def build_folds(
    candles: list[dict[str, Any]],
    *,
    family: str,
    horizon: int,
    train_end: int,
    stride: int,
    max_folds: int = MAX_FOLDS,
) -> list[dict[str, Any]]:
    """Construct point-in-time folds with labels mature by each forecast origin."""
    _validate_candles(candles, family)
    if not 1 <= horizon <= 36 or stride <= 0 or not 1 <= max_folds <= MAX_FOLDS:
        raise ValueError("Horizon, stride or fold budget out of bounds")
    longest = max(WINDOWS[family])
    if train_end < longest + horizon + MIN_TRAIN_ROWS or train_end + horizon >= len(candles):
        raise ValueError("Training boundary or diagnostic segment is insufficient")
    origins = list(range(train_end, len(candles) - horizon, stride))[:max_folds]
    folds = []
    for origin in origins:
        if not is_temporally_valid_sample(candles, family, origin, horizon):
            raise ValueError("Diagnostic forecast has missing/incomplete feature or target bars")
        train_origins = [
            i
            for i in range(longest, origin - horizon + 1)
            if is_temporally_valid_sample(candles, family, i, horizon)
        ][-MAX_TRAIN_ROWS:]
        if len(train_origins) < MIN_TRAIN_ROWS:
            raise ValueError("Insufficient mature and gap-safe training labels")
        if any(i + horizon > origin for i in train_origins):
            raise RuntimeError("Immature target leakage detected")
        x = [feature_vector(candles, i, family) for i in train_origins]
        y = [
            math.log(float(candles[i + horizon]["close"]) / float(candles[i]["close"]))
            for i in train_origins
        ]
        forecast_x = feature_vector(candles, origin, family)
        if any(not math.isfinite(v) for row in [*x, forecast_x] for v in row):
            raise ValueError("Nonfinite features")
        folds.append(
            {
                "origin": origin,
                "last_train_target_index": max(train_origins) + horizon,
                "x": x,
                "y": y,
                "forecast_x": forecast_x,
            }
        )
    if not folds:
        raise ValueError("No eligible exploratory forecast origins")
    return folds


def _new_estimator() -> Any:
    try:
        module = importlib.import_module("catboost")
    except ImportError as exc:
        raise RuntimeError(
            "Optional CatBoost is not installed. Install catboost in an isolated "
            "research environment; do not change production dependencies."
        ) from exc
    return module.CatBoostRegressor(
        iterations=120,
        depth=4,
        learning_rate=0.03,
        l2_leaf_reg=4.0,
        loss_function="RMSE",
        random_seed=SEED,
        thread_count=1,
        bootstrap_type="No",
        random_strength=0.0,
        allow_writing_files=False,
        verbose=False,
    )


def evaluate_exploratory(
    candles: list[dict[str, Any]],
    *,
    family: str,
    horizon: int,
    train_end: int,
    stride: int,
    max_folds: int = MAX_FOLDS,
) -> dict[str, Any]:
    folds = build_folds(
        candles, family=family, horizon=horizon, train_end=train_end,
        stride=stride, max_folds=max_folds,
    )
    records = []
    for fold in folds:
        # A fresh model on every fold; no global transforms or fitted state.
        model = _new_estimator()
        model.fit(fold["x"], fold["y"])
        predicted_return = float(model.predict([fold["forecast_x"]])[0])
        if not math.isfinite(predicted_return) or abs(predicted_return) > 20:
            raise ValueError("Nonfinite or unbounded exploratory prediction")
        origin = int(fold["origin"])
        actual = float(candles[origin + horizon]["close"])
        persistent = float(candles[origin]["close"])
        forecast = persistent * math.exp(predicted_return)
        persistence_ape = abs(persistent - actual) / actual
        catboost_ape = abs(forecast - actual) / actual
        records.append(
            {
                "origin_index": origin,
                "origin_timestamp": candles[origin]["timestamp"],
                "last_train_target_index": fold["last_train_target_index"],
                "training_rows": len(fold["y"]),
                "persistence_ape": persistence_ape,
                "catboost_ape": catboost_ape,
                "paired_improvement": persistence_ape - catboost_ape,
            }
        )
    return {
        "status": "EXPLORATORY_ONLY",
        "freeze": "NO_FREEZE",
        "scope": SCOPE,
        "fresh_locked_oos_access": False,
        "v2_locked_oos_used_for_tuning": False,
        "production_promotion": False,
        "family": family,
        "horizon_bars": horizon,
        "train_end": train_end,
        "stride": stride,
        "seed": SEED,
        "model": "CatBoostRegressor (fixed hyperparameters, separate from frozen V3 family)",
        "statistical_claim": "NONE: descriptive paired errors only",
        "n_origins": len(records),
        "mean_paired_improvement": statistics.fmean(r["paired_improvement"] for r in records),
        "paired_records": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enable-exploratory", action="store_true")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--family", choices=tuple(WINDOWS), required=True)
    parser.add_argument("--horizon", type=int, required=True)
    parser.add_argument("--train-end", type=int, required=True)
    parser.add_argument("--stride", type=int, required=True)
    parser.add_argument("--max-folds", type=int, default=MAX_FOLDS)
    args = parser.parse_args()
    if not args.enable_exploratory:
        parser.error("The --enable-exploratory opt-in flag is required")
    output = _safe_path(args.output, suffix=".exploratory.json")
    if output.exists():
        parser.error("Refusing to overwrite an existing artifact")
    candles, source = load_development_slice(args.input)
    report = evaluate_exploratory(
        candles, family=args.family, horizon=args.horizon, train_end=args.train_end,
        stride=args.stride, max_folds=args.max_folds,
    )
    report["source"] = source
    report["input_sha256"] = hashlib.sha256(args.input.read_bytes()).hexdigest()
    # Exclusive create; never overwrite previous or protected evidence.
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(f"EXPLORATORY_ONLY NO_FREEZE wrote {output}")


if __name__ == "__main__":
    main()
