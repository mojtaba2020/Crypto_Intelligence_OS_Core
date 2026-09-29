#!/usr/bin/env python3
"""Leakage-resistant baseline tournament for daily/weekly/monthly horizons."""

from __future__ import annotations

import math
import statistics

from scripts.multitimeframe_features_v3 import WINDOWS, feature_vector

HORIZONS = {"daily": (1, 2, 3), "weekly": (1, 2, 3), "monthly": (1, 3)}
CANDIDATES = ("ridge", "extra_trees", "boosting")


def _fit_ridge(x: list[list[float]], y: list[float], alpha: float = 1.0) -> list[float]:
    try:
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("numpy is required for the tournament") from exc
    matrix = np.asarray(x, dtype=float)
    target = np.asarray(y, dtype=float)
    means = matrix.mean(axis=0)
    scales = matrix.std(axis=0)
    scales[scales == 0.0] = 1.0
    z = (matrix - means) / scales
    design = np.column_stack([np.ones(len(z)), z])
    penalty = np.eye(design.shape[1])
    penalty[0, 0] = 0.0
    beta = np.linalg.solve(design.T @ design + alpha * penalty, design.T @ target)
    return [*beta, *means, *scales]


def _predict_ridge(state: list[float], row: list[float]) -> float:
    import numpy as np

    n = len(row)
    beta = np.asarray(state[: n + 1])
    means = np.asarray(state[n + 1 : 2 * n + 1])
    scales = np.asarray(state[2 * n + 1 :])
    return float(beta[0] + ((np.asarray(row) - means) / scales) @ beta[1:])


def _fit_candidate(name: str, x: list[list[float]], y: list[float]):
    if name == "ridge":
        state = _fit_ridge(x, y)
        return lambda row: _predict_ridge(state, row)
    try:
        from sklearn.ensemble import ExtraTreesRegressor, GradientBoostingRegressor
    except ImportError as exc:
        raise RuntimeError("scikit-learn is required for tree candidates") from exc
    if name == "extra_trees":
        model = ExtraTreesRegressor(
            n_estimators=200, min_samples_leaf=5, random_state=20260929, n_jobs=1
        )
    elif name == "boosting":
        model = GradientBoostingRegressor(
            n_estimators=100, learning_rate=0.05, max_depth=2, random_state=20260929
        )
    else:
        raise ValueError(f"Unknown candidate: {name}")
    model.fit(x, y)
    return model.predict


def _known_training_origins(longest: int, origin: int, horizon: int) -> list[int]:
    """Only labels whose target candle is closed by the forecast origin are knowable."""
    return [i for i in range(longest, origin) if i + horizon <= origin]


def evaluate(
    candles: list[dict[str, float]],
    family: str,
    horizon: int,
    min_train: int,
    step: int,
) -> dict[str, object]:
    longest = max(WINDOWS[family])
    last_origin = len(candles) - horizon - 1
    origins = list(range(longest + min_train, last_origin + 1, step))
    if len(origins) < 20:
        raise ValueError("Insufficient out-of-sample origins")

    candidate_errors = {name: [] for name in CANDIDATES}
    candidate_directions = {name: [] for name in CANDIDATES}
    persistence_errors = []
    for origin in origins:
        train_origins = _known_training_origins(longest, origin, horizon)
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
            predicted_return = (
                float(predictor([row])[0]) if name != "ridge" else float(predictor(row))
            )
            predicted = current * math.exp(predicted_return)
            candidate_errors[name].append(abs(predicted - actual) / actual)
            candidate_directions[name].append((predicted_return >= 0) == (actual >= current))

    results = {}
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
