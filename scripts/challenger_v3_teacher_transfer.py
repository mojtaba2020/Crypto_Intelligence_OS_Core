#!/usr/bin/env python3
"""Controlled knowledge-transfer experiment from the 1w Elastic Net teacher.

Development/validation only. The stable subset is predeclared from Run #34
teacher diagnostics before recipient-model outcomes are inspected.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import multitimeframe_tournament_v2 as tournament
from challenger_v3_feature_ablation import feature_mask
from multitimeframe_features_v3 import feature_names

TEACHER = {"horizon": "1w", "model": "elastic_net", "features": "regime_only_delta"}
RECIPIENTS = (
    "ridge",
    "huber",
    "bayesian_ridge",
    "boosting",
    "hist_gradient_boosting",
    "random_forest",
    "extra_trees",
    "random_forest_sqrt",
    "extra_trees_sqrt",
)
# Predeclared rule: retain teacher features with sign_stability >= 0.90 and
# nonzero_fraction >= 0.90. Run #34 therefore excludes only range_position_13
# (sign stability 0.7826) and retains these six features.
STABLE_FEATURES = (
    "trend_close_vs_sma_4",
    "trend_close_vs_sma_13",
    "trend_sma_4_vs_13",
    "trend_sma_13_vs_26",
    "vol_ratio_4_vs_13",
    "vol_ratio_13_vs_26",
)


def stable_feature_indices() -> list[int]:
    names = feature_names("weekly")
    indices = [names.index(name) for name in STABLE_FEATURES]
    regime = set(feature_mask("weekly", "regime_only_delta"))
    if not set(indices).issubset(regime):
        raise RuntimeError("Teacher subset escaped regime-only feature family")
    return indices


def _evaluate_with_indices(
    candles: list[dict[str, float]], indices: list[int]
) -> dict[str, object]:
    import math
    import statistics

    from multitimeframe_features_v3 import WINDOWS, feature_vector, is_temporally_valid_sample

    family, horizon, min_train, step = "weekly", 1, 260, 4
    longest = max(WINDOWS[family])
    last_origin = len(candles) - horizon - 1
    origins = [
        o
        for o in range(longest + min_train, last_origin + 1, step)
        if is_temporally_valid_sample(candles, family, o, horizon)
    ]
    if len(origins) < 20:
        raise ValueError("Insufficient out-of-sample origins")

    valid = [
        i
        for i in range(longest, len(candles) - horizon)
        if is_temporally_valid_sample(candles, family, i, horizon)
    ]
    features = {i: [feature_vector(candles, i, family)[j] for j in indices] for i in valid}
    labels = {
        i: math.log(float(candles[i + horizon]["close"]) / float(candles[i]["close"]))
        for i in valid
    }

    errors = {name: [] for name in RECIPIENTS}
    persistence: list[float] = []
    paired: list[dict[str, object]] = []
    for origin in origins:
        train = [i for i in valid if i < origin and i + horizon <= origin]
        x, y = [features[i] for i in train], [labels[i] for i in train]
        current, actual = float(candles[origin]["close"]), float(candles[origin + horizon]["close"])
        base = abs(current - actual) / actual
        persistence.append(base)
        row_errors = {}
        for name in RECIPIENTS:
            predictor = tournament._fit_candidate(name, x, y)
            pred_return = tournament._predict_candidate(name, predictor, features[origin])
            err = abs(current * math.exp(pred_return) - actual) / actual
            errors[name].append(err)
            row_errors[name] = err
        paired.append(
            {
                "origin_index": origin,
                "origin_timestamp": candles[origin].get("timestamp"),
                "persistence_error": base,
                "candidate_errors": row_errors,
            }
        )

    candidates = {}
    for name in RECIPIENTS:
        candidates[name] = {
            "mape": statistics.mean(errors[name]),
            "mean_loss_improvement": statistics.mean(
                b - e for b, e in zip(persistence, errors[name], strict=True)
            ),
        }
    return {
        "samples": len(origins),
        "persistence_mape": statistics.mean(persistence),
        "candidates": candidates,
        "origin_level_paired_losses": paired,
    }


def build_report(candles: list[dict[str, float]]) -> dict[str, object]:
    indices = stable_feature_indices()
    result = _evaluate_with_indices(candles, indices)
    return {
        "status": "CHALLENGER_V3_1W_TEACHER_TRANSFER_DEVELOPMENT_ONLY",
        "scope": "development_validation_only",
        "teacher": TEACHER,
        "transfer_policy": {
            "source_run": 34,
            "selection_rule": "sign_stability>=0.90 and nonzero_fraction>=0.90",
            "stable_features": list(STABLE_FEATURES),
            "excluded_teacher_feature": "range_position_13",
            "recipient_models": list(RECIPIENTS),
            "coefficients_transferred": False,
            "information_structure_only": True,
        },
        "fresh_locked_oos_access": False,
        "v2_locked_oos_used_for_tuning": False,
        "confirmatory": False,
        "production_eligible": False,
        "result": result,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    candles = json.loads(Path(args.data).read_text())
    report = build_report(candles)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True))
    print(json.dumps({"status": report["status"], "samples": report["result"]["samples"]}))


if __name__ == "__main__":
    main()
