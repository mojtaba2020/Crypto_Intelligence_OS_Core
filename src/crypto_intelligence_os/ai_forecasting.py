"""Trainable, offline BTC daily forecasting baseline with chronological holdout.

Uses only completed daily closes available at the forecast origin. This is a
small regularized linear ML model, not a verified profitable trading strategy.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import exp, isfinite, log, sqrt


@dataclass(frozen=True)
class Observation:
    day: date
    close: float


@dataclass(frozen=True)
class TrainedModel:
    horizon_days: int
    intercept: float
    coefficients: tuple[float, float, float]
    train_examples: int
    last_training_target: date


@dataclass(frozen=True)
class Backtest:
    horizon_days: int
    train_examples: int
    test_examples: int
    model_mae: float
    persistence_mae: float
    model_mape_pct: float
    persistence_mape_pct: float
    model: TrainedModel


def _validate(history: tuple[Observation, ...]) -> None:
    if not history:
        raise ValueError("Empty history")
    for point in history:
        if not isfinite(point.close) or point.close <= 0:
            raise ValueError("Closes must be finite and positive")
    for previous, current in zip(history, history[1:], strict=False):
        if (current.day - previous.day).days != 1:
            raise ValueError("Daily observations must be contiguous and strictly ordered")


def _features(history: tuple[Observation, ...], index: int) -> tuple[float, float, float]:
    current = log(history[index].close)
    return (
        current - log(history[index - 1].close),
        current - log(history[index - 7].close),
        current - log(history[index - 14].close),
    )


def _examples(
    history: tuple[Observation, ...], horizon_days: int
) -> tuple[tuple[int, tuple[float, float, float], float], ...]:
    if horizon_days < 1:
        raise ValueError("Horizon must be positive")
    return tuple(
        (
            index,
            _features(history, index),
            log(history[index + horizon_days].close / history[index].close),
        )
        for index in range(14, len(history) - horizon_days)
    )


def _solve(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    """Solve a small ridge normal equation using pivoted Gaussian elimination."""
    size = len(rhs)
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(matrix[row][column]))
        matrix[column], matrix[pivot] = matrix[pivot], matrix[column]
        rhs[column], rhs[pivot] = rhs[pivot], rhs[column]
        if abs(matrix[column][column]) < 1e-12:
            raise ValueError("Singular model matrix")
        scale = matrix[column][column]
        for index in range(column, size):
            matrix[column][index] /= scale
        rhs[column] /= scale
        for row in range(size):
            if row == column:
                continue
            factor = matrix[row][column]
            for index in range(column, size):
                matrix[row][index] -= factor * matrix[column][index]
            rhs[row] -= factor * rhs[column]
    return rhs


def train(
    history: tuple[Observation, ...],
    *,
    horizon_days: int = 7,
    as_of_index: int | None = None,
    minimum_examples: int = 30,
    ridge: float = 1.0,
) -> TrainedModel:
    """Train using only labels whose target date is at or before as_of_index."""
    _validate(history)
    if minimum_examples < 4 or ridge <= 0:
        raise ValueError("Invalid training configuration")
    cutoff = len(history) - 1 if as_of_index is None else as_of_index
    if cutoff < 0 or cutoff >= len(history):
        raise ValueError("Invalid as-of index")
    rows = [
        (index, features, target)
        for index, features, target in _examples(history, horizon_days)
        if index + horizon_days <= cutoff
    ]
    if len(rows) < minimum_examples:
        raise ValueError("Insufficient resolved training examples")
    # Scale features from training only, avoiding magnitude-sensitive fitting.
    means = [sum(features[j] for _, features, _ in rows) / len(rows) for j in range(3)]
    scales = [
        max(
            sqrt(
                sum((features[j] - means[j]) ** 2 for _, features, _ in rows)
                / len(rows)
            ),
            1e-8,
        )
        for j in range(3)
    ]
    design = [
        [1.0, *((features[j] - means[j]) / scales[j] for j in range(3))]
        for _, features, _ in rows
    ]
    matrix = [
        [
            sum(vector[i] * vector[j] for vector in design)
            + (ridge if i == j and i > 0 else 0.0)
            for j in range(4)
        ]
        for i in range(4)
    ]
    rhs = [
        sum(vector[i] * target for vector, (_, _, target) in zip(design, rows, strict=True))
        for i in range(4)
    ]
    weights = _solve(matrix, rhs)
    coefficients = tuple(weights[j + 1] / scales[j] for j in range(3))
    intercept = weights[0] - sum(coefficients[j] * means[j] for j in range(3))
    return TrainedModel(
        horizon_days=horizon_days,
        intercept=intercept,
        coefficients=coefficients,
        train_examples=len(rows),
        last_training_target=history[cutoff].day,
    )


def predict(
    model: TrainedModel, history: tuple[Observation, ...]
) -> float:
    """Predict future close using the most recent completed daily observation."""
    _validate(history)
    if len(history) < 15:
        raise ValueError("At least 15 completed daily closes required")
    features = _features(history, len(history) - 1)
    predicted_log_return = model.intercept + sum(
        weight * feature
        for weight, feature in zip(model.coefficients, features, strict=True)
    )
    return history[-1].close * exp(predicted_log_return)


def walk_forward(
    history: tuple[Observation, ...],
    *,
    horizon_days: int = 7,
    minimum_examples: int = 30,
    minimum_test_examples: int = 10,
) -> Backtest:
    """Expanding-window evaluation with labels resolved by each forecast date."""
    _validate(history)
    if minimum_test_examples < 1:
        raise ValueError("minimum_test_examples must be positive")
    first_origin = 14 + horizon_days + minimum_examples - 1
    last_origin = len(history) - horizon_days - 1
    if last_origin - first_origin + 1 < minimum_test_examples:
        raise ValueError("Insufficient chronological holdout examples")
    errors: list[tuple[float, float, float, float]] = []
    for origin in range(first_origin, last_origin + 1):
        model = train(
            history[: origin + 1],
            horizon_days=horizon_days,
            minimum_examples=minimum_examples,
        )
        estimate = predict(model, history[: origin + 1])
        actual = history[origin + horizon_days].close
        baseline = history[origin].close
        errors.append(
            (
                abs(estimate - actual),
                abs(baseline - actual),
                100 * abs(estimate - actual) / actual,
                100 * abs(baseline - actual) / actual,
            )
        )
    count = len(errors)
    final_model = train(
        history,
        horizon_days=horizon_days,
        minimum_examples=minimum_examples,
    )
    return Backtest(
        horizon_days=horizon_days,
        train_examples=final_model.train_examples,
        test_examples=count,
        model_mae=sum(row[0] for row in errors) / count,
        persistence_mae=sum(row[1] for row in errors) / count,
        model_mape_pct=sum(row[2] for row in errors) / count,
        persistence_mape_pct=sum(row[3] for row in errors) / count,
        model=final_model,
    )
