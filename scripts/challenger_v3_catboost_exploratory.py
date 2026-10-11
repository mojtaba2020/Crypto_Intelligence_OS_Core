#!/usr/bin/env python3
"""Opt-in, development-only CatBoost research outside the frozen V3 family.

This is NOT evidence of statistical significance, champion status or permission
for a locked-OOS read. Only pre-extracted development/validation slices are allowed.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import os
import json
import math
import statistics
from datetime import UTC, datetime
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


MAX_INPUT_BYTES = 10_000_000
MANIFEST_FIELDS = {
    "scope",
    "source",
    "family",
    "slice_sha256",
    "source_interval_seconds",
    "first_open_timestamp",
    "last_open_timestamp",
    "approved_dev_end_exclusive",
    "extraction_asof_timestamp",
    "source_audit_sha256",
}


def _safe_path(path: Path, *, root: Path, suffix: str) -> Path:
    """Contain a non-symlinked path beneath an explicitly approved root."""
    if not path.is_absolute() or not root.is_absolute() or not root.is_dir():
        raise ValueError("Paths must be absolute, with an existing approved root")
    if ".." in path.parts or not path.name.endswith(suffix):
        raise ValueError("Traversal or invalid file suffix")
    for item in (root, path):
        current = Path(item.anchor)
        for part in item.parts[1:]:
            current /= part
            if current.is_symlink():
                raise ValueError("Symlinked path or parent directory is forbidden")
    approved_root = root.resolve(strict=True)
    resolved = path.resolve(strict=False)
    if not resolved.is_relative_to(approved_root) or resolved == approved_root:
        raise ValueError("Path is outside the approved root")
    if not resolved.parent.is_dir():
        raise ValueError("Parent directory does not exist")
    relative = resolved.relative_to(approved_root)
    if any(word in part.lower() for part in relative.parts for word in FORBIDDEN_PATH_PARTS):
        raise ValueError("Reserved/locked/production paths are forbidden")
    return resolved


def _read_bounded(path: Path, limit: int) -> bytes:
    """Read precisely one regular file buffer, without following final symlinks."""
    import stat

    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("Not a regular file")
        content = bytearray()
        while len(content) <= limit:
            part = os.read(descriptor, min(65_536, limit + 1 - len(content)))
            if not part:
                break
            content.extend(part)
        if len(content) > limit:
            raise ValueError("Input file exceeds size limit")
        return bytes(content)
    finally:
        os.close(descriptor)


def _parse_json(raw: bytes) -> Any:
    return json.loads(
        raw.decode("utf-8"),
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")),
    )


def _bar_end(open_timestamp: int, family: str) -> int:
    return _next_period_timestamp(open_timestamp, family)


def _canonical_open(open_timestamp: int, family: str) -> bool:
    date = datetime.fromtimestamp(open_timestamp, tz=UTC)
    if date.hour or date.minute or date.second or date.microsecond:
        return False
    if family == "weekly":
        return date.weekday() == 0
    if family == "monthly":
        return date.day == 1
    return True


def _approved_manifest(
    path: Path, root: Path, digest: str, family: str
) -> dict[str, Any]:
    path = _safe_path(path, root=root, suffix=".audit.json")
    raw = _read_bounded(path, 40_000)
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("A pinned lowercase audit manifest SHA-256 is required")
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("Audit manifest SHA-256 mismatch")
    manifest = _parse_json(raw)
    if not isinstance(manifest, dict) or set(manifest) != MANIFEST_FIELDS:
        raise ValueError("Invalid closed-schema audit manifest")
    if manifest["scope"] != SCOPE or manifest["family"] != family:
        raise ValueError("Manifest does not authorize requested data scope/family")
    for name in ("slice_sha256", "source_audit_sha256"):
        val = manifest[name]
        if not isinstance(val, str) or len(val) != 64 or any(
            c not in "0123456789abcdef" for c in val
        ):
            raise ValueError("Missing pinned data provenance digest")
    if not isinstance(manifest["source"], str) or not manifest["source"].strip():
        raise ValueError("Missing audited source identity")
    for name in (
        "source_interval_seconds",
        "first_open_timestamp",
        "last_open_timestamp",
        "approved_dev_end_exclusive",
        "extraction_asof_timestamp",
    ):
        if type(manifest[name]) is not int or manifest[name] <= 0:
            raise ValueError("Invalid audited data boundary")
    if manifest["source_interval_seconds"] not in (3600, 86400):
        raise ValueError("Source interval must be approved hourly or daily")
    if not (
        manifest["first_open_timestamp"] <= manifest["last_open_timestamp"]
        < manifest["approved_dev_end_exclusive"]
        <= manifest["extraction_asof_timestamp"]
    ):
        raise ValueError("Inconsistent manifest timestamps")
    return manifest

def _validate_candles(
    candles: list[dict[str, Any]], family: str, source_interval_seconds: int = 3600
) -> None:
    if family not in WINDOWS:
        raise ValueError("Unsupported time family")
    if source_interval_seconds not in (3600, 86400):
        raise ValueError("Unsupported source interval")
    if len(candles) <= max(WINDOWS[family]) + MIN_TRAIN_ROWS + 1:
        raise ValueError("Insufficient development-only candles")
    last_timestamp: int | None = None
    for row in candles:
        if not isinstance(row, dict) or row.get("is_complete") is not True:
            raise ValueError("Incomplete candles forbidden: never interpolate or backfill")
        stamp = row.get("timestamp")
        if type(stamp) not in (int, float) or not math.isfinite(stamp) or int(stamp) != stamp:
            raise ValueError("Every candle requires a valid integer timestamp")
        timestamp = int(stamp)
        if not _canonical_open(timestamp, family):
            raise ValueError("Noncanonical UTC bar-opening calendar")
        if last_timestamp is not None and timestamp != _bar_end(last_timestamp, family):
            raise ValueError("Noncontiguous candle calendar: no interpolation allowed")
        last_timestamp = timestamp
        duration = _bar_end(timestamp, family) - timestamp
        if duration % source_interval_seconds:
            raise ValueError("Source interval does not divide candle duration")
        expected = duration // source_interval_seconds
        if (
            type(row.get("source_bars")) is not int
            or type(row.get("expected_source_bars")) is not int
            or row["source_bars"] != expected
            or row["expected_source_bars"] != expected
        ):
            raise ValueError("Source-bars completeness evidence mismatch")
        for name in ("open", "high", "low", "close", "volume"):
            value = row.get(name)
            if type(value) not in (float, int) or not math.isfinite(value):
                raise ValueError(f"Nonfinite or invalid candle {name}")
        opening, high, low, close = (float(row[k]) for k in ("open", "high", "low", "close"))
        if (
            low <= 0
            or min(opening, close) <= 0
            or high < max(opening, close)
            or low > min(opening, close)
            or float(row["volume"]) < 0
        ):
            raise ValueError("Invalid OHLCV bounds")


def load_development_slice(
    path: Path,
    *,
    approved_root: Path,
    manifest_path: Path,
    manifest_root: Path,
    manifest_sha256: str,
    family: str,
) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    """Load exact pinned bytes; scope claims are NOT independent provenance proof."""
    manifest = _approved_manifest(manifest_path, manifest_root, manifest_sha256, family)
    path = _safe_path(path, root=approved_root, suffix=".development.json")
    raw = _read_bounded(path, MAX_INPUT_BYTES)
    input_sha256 = hashlib.sha256(raw).hexdigest()
    if input_sha256 != manifest["slice_sha256"]:
        raise ValueError("Development slice SHA-256 does not match audit manifest")
    payload = _parse_json(raw)
    if not isinstance(payload, dict) or set(payload) != {"scope", "source", "candles"}:
        raise ValueError("Expected closed-schema development-slice payload")
    if payload["scope"] != SCOPE:
        raise ValueError("Fresh Locked OOS or other non-development scope is forbidden")
    if payload["source"] != manifest["source"]:
        raise ValueError("Development source differs from approved manifest")
    candles = payload["candles"]
    if not isinstance(candles, list) or not all(isinstance(item, dict) for item in candles):
        raise ValueError("Development candles must be a list of objects")
    _validate_candles(candles, family, manifest["source_interval_seconds"])
    if (
        int(candles[0]["timestamp"]) != manifest["first_open_timestamp"]
        or int(candles[-1]["timestamp"]) != manifest["last_open_timestamp"]
        or _bar_end(int(candles[-1]["timestamp"]), family)
        > manifest["approved_dev_end_exclusive"]
        or _bar_end(int(candles[-1]["timestamp"]), family)
        > manifest["extraction_asof_timestamp"]
    ):
        raise ValueError("Candle availability exceeds audited boundary")
    return candles, manifest, input_sha256

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
        candles,
        family=family,
        horizon=horizon,
        train_end=train_end,
        stride=stride,
        max_folds=max_folds,
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
        candles,
        family=args.family,
        horizon=args.horizon,
        train_end=args.train_end,
        stride=args.stride,
        max_folds=args.max_folds,
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
