#!/usr/bin/env python3
"""Explain why the 1w Elastic Net regime challenger works, without touching locked OOS.

Development/validation diagnostic only.  It reconstructs the exact point-in-time
weekly training sequence, measures standardized Elastic Net coefficient
stability, and stress-tests whether paired improvement is concentrated in a few
forecast origins.  The output is evidence for transfer hypotheses, never a
promotion decision.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path

from sklearn.linear_model import ElasticNet
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from challenger_v3_feature_ablation import apply_mask, feature_mask
from multitimeframe_features_v3 import feature_names, feature_vector, is_temporally_valid_sample
from multitimeframe_split_v1 import chronological_split

SEED = 20260929


def _load(path: Path) -> list[dict[str, float]]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("Expected candle list")
    return rows


def _fit(x: list[list[float]], y: list[float]):
    model = make_pipeline(
        StandardScaler(),
        ElasticNet(alpha=0.0001, l1_ratio=0.25, max_iter=5000, random_state=SEED),
    )
    model.fit(x, y)
    return model


def _sign_stability(values: list[float]) -> float:
    nonzero = [v for v in values if abs(v) > 1e-12]
    if not nonzero:
        return 0.0
    positive = sum(v > 0 for v in nonzero)
    return max(positive, len(nonzero) - positive) / len(nonzero)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()

    candles = _load(args.data)
    family, horizon, min_train, step = "weekly", 1, 260, 4
    split = chronological_split(len(candles), min_train, horizon)
    view = candles[: split.validation_end]
    mask = feature_mask(family, "regime_only_delta")
    names = [feature_names(family)[i] for i in mask]
    longest = 52
    valid = [
        i
        for i in range(longest, len(view) - horizon)
        if is_temporally_valid_sample(view, family, i, horizon)
    ]
    cache = {i: apply_mask(feature_vector(view, i, family), mask) for i in valid}
    labels = {
        i: math.log(float(view[i + horizon]["close"]) / float(view[i]["close"])) for i in valid
    }
    origins = [
        i
        for i in range(longest + min_train, len(view) - horizon, step)
        if is_temporally_valid_sample(view, family, i, horizon)
    ]
    if len(origins) < 20:
        raise ValueError("Insufficient diagnostic origins")

    coefficient_history = {name: [] for name in names}
    paired = []
    origin_rows = []
    for origin in origins:
        train = [i for i in valid if i < origin and i + horizon <= origin]
        x, y = [cache[i] for i in train], [labels[i] for i in train]
        model = _fit(x, y)
        coefs = list(model.named_steps["elasticnet"].coef_)
        for name, coef in zip(names, coefs, strict=True):
            coefficient_history[name].append(float(coef))

        current = float(view[origin]["close"])
        actual = float(view[origin + horizon]["close"])
        predicted_return = float(model.predict([cache[origin]])[0])
        predicted = current * math.exp(predicted_return)
        base_error = abs(current - actual) / actual
        model_error = abs(predicted - actual) / actual
        improvement = base_error - model_error
        paired.append(improvement)
        origin_rows.append(
            {
                "origin_index": origin,
                "origin_timestamp": view[origin].get("timestamp"),
                "improvement": improvement,
                "persistence_error": base_error,
                "model_error": model_error,
            }
        )

    feature_diagnostics = []
    for name in names:
        vals = coefficient_history[name]
        feature_diagnostics.append(
            {
                "feature": name,
                "mean_standardized_coefficient": statistics.fmean(vals),
                "median_standardized_coefficient": statistics.median(vals),
                "mean_absolute_coefficient": statistics.fmean(abs(v) for v in vals),
                "sign_stability": _sign_stability(vals),
                "nonzero_fraction": statistics.fmean(abs(v) > 1e-12 for v in vals),
            }
        )
    feature_diagnostics.sort(key=lambda row: row["mean_absolute_coefficient"], reverse=True)

    ranked = sorted(origin_rows, key=lambda row: row["improvement"], reverse=True)
    total_positive = sum(max(0.0, x) for x in paired)
    top3_positive = sum(max(0.0, row["improvement"]) for row in ranked[:3])
    trimmed = sorted(paired)[1:-1] if len(paired) > 2 else paired
    leave_one_out_means = [
        statistics.fmean(paired[:i] + paired[i + 1 :]) for i in range(len(paired))
    ]

    report = {
        "status": "CHALLENGER_V3_1W_TEACHER_DIAGNOSTIC_ONLY",
        "scope": "development_validation_only",
        "teacher": {"horizon": "1w", "model": "elastic_net", "features": "regime_only_delta"},
        "fresh_locked_oos_access": False,
        "v2_locked_oos_used_for_tuning": False,
        "production_eligible": False,
        "samples": len(origins),
        "mean_paired_improvement": statistics.fmean(paired),
        "median_paired_improvement": statistics.median(paired),
        "win_fraction": statistics.fmean(x > 0 for x in paired),
        "trimmed_mean_improvement": statistics.fmean(trimmed),
        "worst_leave_one_out_mean": min(leave_one_out_means),
        "best_leave_one_out_mean": max(leave_one_out_means),
        "top3_share_of_positive_improvement": (
            top3_positive / total_positive if total_positive > 0 else None
        ),
        "feature_diagnostics": feature_diagnostics,
        "top_origins": ranked[:5],
        "bottom_origins": ranked[-5:],
        "transfer_rule": {
            "principle": "transfer information structure, not Elastic Net coefficients",
            "eligible_if": [
                "feature has stable coefficient sign across walk-forward fits",
                "improvement is not dominated by a few origins",
                "leave-one-out and trimmed mean remain directionally positive",
            ],
            "recipient_models": [
                "ridge",
                "huber",
                "bayesian_ridge",
                "boosting",
                "hist_gradient_boosting",
                "random_forest",
                "extra_trees",
                "random_forest_sqrt",
                "extra_trees_sqrt",
            ],
            "next_test": "retrain recipients on teacher-derived stable feature subset under identical causal walk-forward splits",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
