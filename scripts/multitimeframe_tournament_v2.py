#!/usr/bin/env python3
"""Challenger V2 classical-model development lane.

This module is deliberately separate from the frozen V1 evidence tournament.
It may be used for development/validation research only; it does not authorize
locked-OOS reuse, champion selection, or production promotion.
"""

from __future__ import annotations

import math
import statistics

import multitimeframe_tournament_v1 as v1

HORIZONS = v1.HORIZONS
CANDIDATES = (
    "ridge",
    "elastic_net",
    "extra_trees",
    "random_forest",
    "hist_gradient_boosting",
    "boosting",
)


def _fit_candidate(name: str, x: list[list[float]], y: list[float]):
    if name in {"ridge", "extra_trees", "boosting"}:
        return v1._fit_candidate(name, x, y)

    try:
        from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
        from sklearn.linear_model import ElasticNet
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:
        raise RuntimeError("scikit-learn is required for Challenger V2") from exc

    if name == "elastic_net":
        model = make_pipeline(
            StandardScaler(),
            ElasticNet(alpha=0.0001, l1_ratio=0.25, max_iter=5000, random_state=20260929),
        )
    elif name == "random_forest":
        model = RandomForestRegressor(
            n_estimators=200,
            min_samples_leaf=5,
            max_features=0.75,
            random_state=20260929,
            n_jobs=-1,
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
        raise ValueError(f"Unknown Challenger V2 candidate: {name}")

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
) -> dict[str, object]:
    """Run V2 locally without mutating the frozen V1 module."""
    from scripts.multitimeframe_features_v3 import (
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

    candidate_errors = {name: [] for name in CANDIDATES}
    candidate_directions = {name: [] for name in CANDIDATES}
    persistence_errors: list[float] = []

    for origin in origins:
        train_origins = [
            i
            for i in v1._known_training_origins(longest, origin, horizon)
            if is_temporally_valid_sample(candles, family, i, horizon)
        ]
        x = [feature_vector(candles, i, family) for i in train_origins]
        y = [
            math.log(float(candles[i + horizon]["close"]) / float(candles[i]["close"]))
            for i in train_origins
        ]
        if len(x) != len(y):
            raise RuntimeError("Feature/label alignment invariant violated")

        current = float(candles[origin]["close"])
        actual = float(candles[origin + horizon]["close"])
        persistence_errors.append(abs(current - actual) / actual)
        row = feature_vector(candles, origin, family)

        for name in CANDIDATES:
            predictor = _fit_candidate(name, x, y)
            predicted_return = _predict_candidate(name, predictor, row)
            predicted = current * math.exp(predicted_return)
            candidate_errors[name].append(abs(predicted - actual) / actual)
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
    }
