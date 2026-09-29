#!/usr/bin/env python3
"""Deterministic live inference adapters matching locked hourly tournament families."""

from __future__ import annotations

import math

try:
    from .train_hourly_boosting_tournament import _boost_predict
    from .train_hourly_boosting_tournament import _features as boost_features
    from .train_hourly_extra_trees_tournament import _features as tree_features
    from .train_hourly_extra_trees_tournament import _forest_predict
    from .train_hourly_ridge_tournament import _features as ridge_features
    from .train_hourly_ridge_tournament import _ridge_fit
except ImportError:
    from train_hourly_boosting_tournament import _boost_predict
    from train_hourly_boosting_tournament import _features as boost_features
    from train_hourly_extra_trees_tournament import _features as tree_features
    from train_hourly_extra_trees_tournament import _forest_predict
    from train_hourly_ridge_tournament import _features as ridge_features
    from train_hourly_ridge_tournament import _ridge_fit

SUPPORTED = ("ridge", "extra_trees", "boosting")
HORIZONS = (1, 2, 3, 4, 12)


def predict(model: str, closes: list[float], horizon: int) -> float:
    if model not in SUPPORTED:
        raise ValueError("Unsupported hourly model: " + model)
    if horizon not in HORIZONS:
        raise ValueError("Unsupported hourly horizon")
    if len(closes) < 241 or any(value <= 0 for value in closes):
        raise ValueError("Need >=241 positive closed hourly prices")
    test_origin = len(closes) - 1
    features = []
    targets = []
    feature_fn = {
        "ridge": ridge_features,
        "extra_trees": tree_features,
        "boosting": boost_features,
    }[model]
    for origin in range(48, test_origin - horizon + 1):
        features.append(feature_fn(closes, origin))
        targets.append(math.log(closes[origin + horizon] / closes[origin]))
    current_features = feature_fn(closes, test_origin)
    if model == "ridge":
        weights = _ridge_fit(features, targets, 1.0)
        predicted_return = sum(
            weight * value for weight, value in zip(weights, current_features, strict=True)
        )
    elif model == "extra_trees":
        predicted_return = _forest_predict(
            features,
            targets,
            current_features,
            seed=10_000 * horizon + test_origin,
        )
    else:
        predicted_return = _boost_predict(features, targets, current_features)
    return closes[-1] * math.exp(predicted_return)
