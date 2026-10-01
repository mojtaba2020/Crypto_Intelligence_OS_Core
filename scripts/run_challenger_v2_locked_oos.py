#!/usr/bin/env python3
"""Single-use locked-OOS judge for the frozen Challenger V2 classical lane."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
from pathlib import Path

from scripts.multitimeframe_data_v1 import load_candles
from scripts.multitimeframe_features_v3 import WINDOWS, feature_vector, is_temporally_valid_sample
from scripts.multitimeframe_lab_v1 import SPECS
from scripts.multitimeframe_split_v1 import chronological_split
from scripts.multitimeframe_tournament_v1 import _known_training_origins
from scripts.multitimeframe_tournament_v2 import _fit_candidate, _predict_candidate

FROZEN = {
    "1d": "boosting",
    "2d": "boosting",
    "3d": "boosting",
    "1w": "extra_trees",
    "2w": "ridge",
    "3w": "ridge",
}
ALPHA = 0.05
BOOTSTRAP_REPS = 10000
SEED = 20260930


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mbb_pvalue_and_ci(diffs: list[float], block: int) -> tuple[float, list[float]]:
    """Dependence-aware moving-block bootstrap of mean(base_loss-model_loss)."""
    n = len(diffs)
    if n < 2:
        raise ValueError("Need at least two locked-OOS origins")
    b = max(1, min(block, n))
    rng = random.Random(SEED)  # noqa: S311 -- deterministic scientific resampling, not crypto
    starts = list(range(0, n - b + 1))
    observed = statistics.mean(diffs)
    centered = [x - observed for x in diffs]
    boot_means: list[float] = []
    null_means: list[float] = []
    for _ in range(BOOTSTRAP_REPS):
        sample: list[float] = []
        null_sample: list[float] = []
        while len(sample) < n:
            s = rng.choice(starts)
            sample.extend(diffs[s : s + b])
            null_sample.extend(centered[s : s + b])
        boot_means.append(statistics.mean(sample[:n]))
        null_means.append(statistics.mean(null_sample[:n]))
    boot_means.sort()
    lo = boot_means[int(0.025 * BOOTSTRAP_REPS)]
    hi = boot_means[int(0.975 * BOOTSTRAP_REPS) - 1]
    p = (1 + sum(x >= observed for x in null_means)) / (BOOTSTRAP_REPS + 1)
    return p, [lo, hi]


def _holm(rows: list[dict[str, object]]) -> None:
    ordered = sorted(rows, key=lambda r: float(r["p_value"]))
    m = len(ordered)
    still_rejecting = True
    for rank, row in enumerate(ordered, start=1):
        threshold = ALPHA / (m - rank + 1)
        reject = still_rejecting and float(row["p_value"]) <= threshold
        row["holm_threshold"] = threshold
        row["holm_reject"] = reject
        if not reject:
            still_rejecting = False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--exchange", default="bitstamp")
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    rows: list[dict[str, object]] = []
    for spec in SPECS:
        if spec.label not in FROZEN:
            continue
        path = args.data_dir / f"{args.exchange}_{spec.source_timeframe}.json"
        candles = load_candles(path)
        split = chronological_split(len(candles), spec.minimum_history_bars, spec.horizon_bars)
        origins = [
            o
            for o in range(split.validation_end, split.locked_test_end, spec.evaluation_step_bars)
            if is_temporally_valid_sample(candles, spec.family, o, spec.horizon_bars)
        ]
        longest = max(WINDOWS[spec.family])
        model_errors: list[float] = []
        base_errors: list[float] = []
        directions: list[bool] = []
        candidate = FROZEN[spec.label]
        for origin in origins:
            train_origins = [
                i
                for i in _known_training_origins(longest, origin, spec.horizon_bars)
                if is_temporally_valid_sample(candles, spec.family, i, spec.horizon_bars)
            ]
            x = [feature_vector(candles, i, spec.family) for i in train_origins]
            y = [
                math.log(
                    float(candles[i + spec.horizon_bars]["close"]) / float(candles[i]["close"])
                )
                for i in train_origins
            ]
            predictor = _fit_candidate(candidate, x, y)
            row = feature_vector(candles, origin, spec.family)
            predicted_return = _predict_candidate(candidate, predictor, row)
            current = float(candles[origin]["close"])
            actual = float(candles[origin + spec.horizon_bars]["close"])
            predicted = current * math.exp(predicted_return)
            model_errors.append(abs(predicted - actual) / actual)
            base_errors.append(abs(current - actual) / actual)
            directions.append((predicted_return >= 0) == (actual >= current))
        if not origins:
            raise ValueError(f"No locked-OOS origins for {spec.label}")
        diffs = [b - m for b, m in zip(base_errors, model_errors, strict=True)]
        p, ci = _mbb_pvalue_and_ci(diffs, spec.bootstrap_block_bars)
        rows.append({
            "horizon": spec.label,
            "candidate": candidate,
            "dataset_sha256": _sha(path),
            "locked_boundary": {"start": split.validation_end, "end": split.locked_test_end},
            "samples": len(origins),
            "model_mape": statistics.mean(model_errors),
            "persistence_mape": statistics.mean(base_errors),
            "mean_loss_improvement": statistics.mean(diffs),
            "improvement_ci95": ci,
            "p_value": p,
            "direction_accuracy": statistics.mean(directions),
        })

    _holm(rows)
    for row in rows:
        row["passes_statistical_gate"] = bool(
            float(row["mean_loss_improvement"]) > 0
            and float(row["improvement_ci95"][0]) > 0
            and row["holm_reject"]
        )

    report = {
        "status": "CHALLENGER_V2_FRESH_LOCKED_OOS_CONSUMED",
        "freeze_record": "research/CHALLENGER_V2_FREEZE.md",
        "exchange": args.exchange,
        "bootstrap": {"method": "moving_block", "repetitions": BOOTSTRAP_REPS, "seed": SEED},
        "multiplicity": {"method": "holm_bonferroni", "alpha": ALPHA, "family": list(FROZEN)},
        "results": rows,
        "production_promotion": False,
        "next_gate": "independent_exchange_replication for statistical-gate passers only",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
