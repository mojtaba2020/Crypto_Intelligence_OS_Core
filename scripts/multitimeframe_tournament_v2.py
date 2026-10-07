#!/usr/bin/env python3
"""Challenger V2 classical-model development lane.

This module is deliberately separate from the frozen V1 evidence tournament.
It may be used for development/validation research only; it does not authorize
locked-OOS reuse, champion selection, or production promotion.
"""

from __future__ import annotations

import math
import statistics

try:
    from scripts import multitimeframe_tournament_v1 as v1
except ModuleNotFoundError:
    import multitimeframe_tournament_v1 as v1

HORIZONS = v1.HORIZONS
CANDIDATES = (
    "ridge",
    "elastic_net",
    "extra_trees",
    "random_forest",
    "hist_gradient_boosting",
    "boosting",
    "huber",
    "bayesian_ridge",
    "random_forest_sqrt",
    "extra_trees_sqrt",
    "gradient_boosting_huber",
    "gradient_boosting_absolute",
    "hist_gradient_boosting_absolute",
    "ada_boost",
    "random_forest_leaf10",
    "extra_trees_leaf10",
)


def _fit_candidate(name: str, x: list[list[float]], y: list[float]):
    if name in {"ridge", "extra_trees", "boosting"}:
        return v1._fit_candidate(name, x, y)

    try:
        from sklearn.ensemble import (
            AdaBoostRegressor,
            ExtraTreesRegressor,
            GradientBoostingRegressor,
            HistGradientBoostingRegressor,
            RandomForestRegressor,
        )
        from sklearn.linear_model import BayesianRidge, ElasticNet, HuberRegressor
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:
        raise RuntimeError("scikit-learn is required for Challenger V2") from exc

    if name == "huber":
        model = make_pipeline(
            StandardScaler(),
            HuberRegressor(epsilon=1.35, alpha=0.0001, max_iter=1000),
        )
    elif name == "bayesian_ridge":
        model = make_pipeline(StandardScaler(), BayesianRidge())
    elif name == "elastic_net":
        model = make_pipeline(
            StandardScaler(),
            ElasticNet(alpha=0.0001, l1_ratio=0.25, max_iter=5000, random_state=20260929),
        )
    elif name == "random_forest_sqrt":
        model = RandomForestRegressor(
            n_estimators=200,
            min_samples_leaf=5,
            max_features="sqrt",
            random_state=20261003,
            n_jobs=2,
        )
    elif name == "extra_trees_sqrt":
        model = ExtraTreesRegressor(
            n_estimators=200,
            min_samples_leaf=5,
            max_features="sqrt",
            random_state=20261003,
            n_jobs=2,
        )
    elif name == "gradient_boosting_huber":
        model = GradientBoostingRegressor(
            loss="huber",
            n_estimators=150,
            learning_rate=0.03,
            max_depth=2,
            min_samples_leaf=8,
            random_state=20261004,
        )
    elif name == "gradient_boosting_absolute":
        model = GradientBoostingRegressor(
            loss="absolute_error",
            n_estimators=150,
            learning_rate=0.03,
            max_depth=2,
            min_samples_leaf=8,
            random_state=20261004,
        )
    elif name == "hist_gradient_boosting_absolute":
        model = HistGradientBoostingRegressor(
            loss="absolute_error",
            learning_rate=0.04,
            max_iter=150,
            max_leaf_nodes=7,
            min_samples_leaf=10,
            l2_regularization=2.0,
            random_state=20261004,
        )
    elif name == "ada_boost":
        model = AdaBoostRegressor(
            n_estimators=150,
            learning_rate=0.03,
            loss="square",
            random_state=20261004,
        )
    elif name == "random_forest_leaf10":
        model = RandomForestRegressor(
            n_estimators=200,
            min_samples_leaf=10,
            max_features=0.75,
            random_state=20261004,
            n_jobs=2,
        )
    elif name == "extra_trees_leaf10":
        model = ExtraTreesRegressor(
            n_estimators=200,
            min_samples_leaf=10,
            max_features=0.75,
            random_state=20261004,
            n_jobs=2,
        )
    elif name == "random_forest":
        model = RandomForestRegressor(
            n_estimators=100,
            min_samples_leaf=5,
            max_features=0.75,
            random_state=20260929,
            n_jobs=2,
        )
    elif name == "hist_gradient_boosting":
        model = HistGradientBoostingRegressor(
            learning_rate=0.05,
            max_iter=150,
            max_leaf_nodes=15,
            l2_regularization=1.0,
            random_state=20260929,
        )
    else:
        raise ValueError(f"Unknown Challenger V3 candidate: {name}")

    model.fit(x, y)
    return model.predict


def _predict_candidate(name: str, predictor, row: list[float]) -> float:
    if name == "ridge":
        return float(predictor(row))
    return float(predictor([row])[0])


def evaluate(
    candles: list[dict[str, float]],
    family: str,
    horizon: int,
    min_train: int,
    step: int,
    feature_ablation: str = "all_features",
) -> dict[str, object]:
    """Run V2 locally without mutating the frozen V1 module."""
    from challenger_v3_feature_ablation import apply_mask, feature_mask
    from multitimeframe_features_v3 import (
        WINDOWS,
        feature_vector,
        is_temporally_valid_sample,
    )

    longest = max(WINDOWS[family])
    last_origin = len(candles) - horizon - 1
    origins = [
        origin
        for origin in range(longest + min_train, last_origin + 1, step)
        if is_temporally_valid_sample(candles, family, origin, horizon)
    ]
    if len(origins) < 20:
        raise ValueError("Insufficient out-of-sample origins")

    # Precompute every valid point-in-time feature/label once. The original
    # implementation rebuilt the full training matrix for every origin, which
    # was scientifically equivalent but needlessly expensive.
    valid_indices = [
        i
        for i in range(longest, len(candles) - horizon)
        if is_temporally_valid_sample(candles, family, i, horizon)
    ]
    mask = feature_mask(family, feature_ablation)
    feature_cache = {i: apply_mask(feature_vector(candles, i, family), mask) for i in valid_indices}
    label_cache = {
        i: math.log(float(candles[i + horizon]["close"]) / float(candles[i]["close"]))
        for i in valid_indices
    }

    candidate_errors = {name: [] for name in CANDIDATES}
    candidate_directions = {name: [] for name in CANDIDATES}
    persistence_errors: list[float] = []
    origin_records: list[dict[str, object]] = []

    for origin in origins:
        train_origins = [i for i in valid_indices if i < origin and i + horizon <= origin]
        x = [feature_cache[i] for i in train_origins]
        y = [label_cache[i] for i in train_origins]
        if len(x) != len(y):
            raise RuntimeError("Feature/label alignment invariant violated")

        current = float(candles[origin]["close"])
        actual = float(candles[origin + horizon]["close"])
        persistence_error = abs(current - actual) / actual
        persistence_errors.append(persistence_error)
        origin_records.append(
            {
                "origin_index": origin,
                "origin_timestamp": candles[origin].get("timestamp"),
                "actual_close": actual,
                "persistence_error": persistence_error,
                "candidate_errors": {},
            }
        )
        row = feature_cache[origin]

        for name in CANDIDATES:
            predictor = _fit_candidate(name, x, y)
            predicted_return = _predict_candidate(name, predictor, row)
            predicted = current * math.exp(predicted_return)
            model_error = abs(predicted - actual) / actual
            candidate_errors[name].append(model_error)
            origin_records[-1]["candidate_errors"][name] = model_error
            candidate_directions[name].append((predicted_return >= 0) == (actual >= current))

    results: dict[str, dict[str, float]] = {}
    for name in CANDIDATES:
        errors = candidate_errors[name]
        results[name] = {
            "mape": statistics.mean(errors),
            "mean_loss_improvement": statistics.mean(
                base - model for base, model in zip(persistence_errors, errors, strict=True)
            ),
            "direction_accuracy": statistics.mean(candidate_directions[name]),
        }
    return {
        "samples": len(origins),
        "persistence_mape": statistics.mean(persistence_errors),
        "candidates": results,
        "origin_level_paired_losses": origin_records,
    }
