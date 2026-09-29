#!/usr/bin/env python3
"""Leakage-resistant baseline tournament for daily/weekly/monthly horizons."""

from __future__ import annotations

import math
import statistics

from scripts.multitimeframe_features_v3 import WINDOWS, feature_vector

HORIZONS = {"daily": (1, 2, 3), "weekly": (1, 2, 3), "monthly": (1, 3)}


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


def evaluate(
    candles: list[dict[str, float]],
    family: str,
    horizon: int,
    min_train: int,
    step: int,
) -> dict[str, float | int]:
    longest = max(WINDOWS[family])
    last_origin = len(candles) - horizon - 1
    origins = list(range(longest + min_train, last_origin + 1, step))
    if len(origins) < 20:
        raise ValueError("Insufficient out-of-sample origins")

    model_errors, persistence_errors, directions = [], [], []
    for origin in origins:
        train_origins = range(longest, origin)
        x = [feature_vector(candles, i, family) for i in train_origins]
        y = [
            math.log(
                float(candles[i + horizon]["close"]) / float(candles[i]["close"])
            )
            for i in train_origins
            if i + horizon < len(candles)
        ]
        x = x[: len(y)]
        state = _fit_ridge(x, y)
        predicted_return = _predict_ridge(state, feature_vector(candles, origin, family))
        current = float(candles[origin]["close"])
        actual = float(candles[origin + horizon]["close"])
        predicted = current * math.exp(predicted_return)
        model_errors.append(abs(predicted - actual) / actual)
        persistence_errors.append(abs(current - actual) / actual)
        directions.append((predicted_return >= 0) == (actual >= current))

    return {
        "samples": len(origins),
        "ridge_mape": statistics.mean(model_errors),
        "persistence_mape": statistics.mean(persistence_errors),
        "mean_loss_improvement": statistics.mean(
            base - model for base, model in zip(persistence_errors, model_errors)
        ),
        "direction_accuracy": statistics.mean(directions),
    }
