"""Research-only hybrid BTC forecast: cycle features, robust ridge, and persistence.

Every feature is computed using observations available at its forecast origin.
The persistence blend is selected on a past-only calibration period.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import exp, isfinite, log, sqrt

from crypto_intelligence_os.ai_forecasting import Observation, _solve, _validate

HALVINGS = (date(2012, 11, 28), date(2016, 7, 9), date(2020, 5, 11), date(2024, 4, 20))
WINDOWS = (7, 30, 90, 180, 365)


@dataclass(frozen=True)
class HybridModel:
    horizon_days: int
    weights: tuple[float, ...]
    means: tuple[float, ...]
    scales: tuple[float, ...]
    blend: float
    train_examples: int
    last_training_target: date


def features(history: tuple[Observation, ...], index: int) -> tuple[float, ...]:
    if index < 365:
        raise ValueError("At least 366 completed daily closes required")
    current = history[index].close
    result = [log(current / history[index - window].close) for window in WINDOWS]
    returns = [
        log(history[j].close / history[j - 1].close)
        for j in range(index - 29, index + 1)
    ]
    average = sum(returns) / len(returns)
    volatility = sqrt(sum((value - average) ** 2 for value in returns) / len(returns))
    result.append(volatility)
    for window in (90, 365):
        closes = [history[j].close for j in range(index - window + 1, index + 1)]
        high, low = max(closes), min(closes)
        result.extend((log(current / high), log(current / low)))
    known_halvings = [day for day in HALVINGS if day <= history[index].day]
    days_since = (history[index].day - known_halvings[-1]).days if known_halvings else 0
    result.extend((days_since / 1461.0, days_since * days_since / (1461.0**2)))
    return tuple(result)


def _fit(
    examples: list[tuple[tuple[float, ...], float]],
    *,
    ridge: float,
) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]:
    dimensions = len(examples[0][0])
    means = tuple(
        sum(row[0][j] for row in examples) / len(examples)
        for j in range(dimensions)
    )
    scales = tuple(
        max(
            sqrt(sum((row[0][j] - means[j]) ** 2 for row in examples) / len(examples)),
            1e-8,
        )
        for j in range(dimensions)
    )
    design = [
        [1.0, *((values[j] - means[j]) / scales[j] for j in range(dimensions))]
        for values, _ in examples
    ]
    targets = [target for _, target in examples]
    matrix = [
        [
            sum(vector[i] * vector[j] for vector in design)
            + (ridge if i == j and i > 0 else 0.0)
            for j in range(dimensions + 1)
        ]
        for i in range(dimensions + 1)
    ]
    rhs = [
        sum(vector[i] * target for vector, target in zip(design, targets, strict=True))
        for i in range(dimensions + 1)
    ]
    return tuple(_solve(matrix, rhs)), means, scales


def _estimate(
    weights: tuple[float, ...],
    means: tuple[float, ...],
    scales: tuple[float, ...],
    values: tuple[float, ...],
) -> float:
    return weights[0] + sum(
        weights[j + 1] * (values[j] - means[j]) / scales[j]
        for j in range(len(values))
    )


def train_hybrid(
    history: tuple[Observation, ...],
    *,
    horizon_days: int = 7,
    ridge: float = 100.0,
    minimum_examples: int = 365,
) -> HybridModel:
    _validate(history)
    if horizon_days < 1 or ridge <= 0 or minimum_examples < 30:
        raise ValueError("Invalid hybrid configuration")
    cutoff = len(history) - 1
    examples = [
        (
            features(history, index),
            log(history[index + horizon_days].close / history[index].close),
        )
        for index in range(365, cutoff - horizon_days + 1)
    ]
    if len(examples) < minimum_examples:
        raise ValueError("Insufficient resolved training labels")

    # A strictly earlier calibration block chooses whether to trust the ML signal.
    calibration = min(365, max(30, len(examples) // 5))
    split = len(examples) - calibration
    blend = 0.0
    if split >= minimum_examples:
        provisional = _fit(examples[:split], ridge=ridge)
        errors = []
        for weight in (0.0, 0.25, 0.5, 0.75, 1.0):
            absolute = sum(
                abs(weight * _estimate(*provisional, values) - target)
                for values, target in examples[split:]
            )
            errors.append((absolute, weight))
        blend = min(errors)[1]
    weights, means, scales = _fit(examples, ridge=ridge)
    return HybridModel(
        horizon_days=horizon_days,
        weights=weights,
        means=means,
        scales=scales,
        blend=blend,
        train_examples=len(examples),
        last_training_target=history[cutoff].day,
    )


def predict_hybrid(model: HybridModel, history: tuple[Observation, ...]) -> float:
    _validate(history)
    signal = _estimate(
        model.weights,
        model.means,
        model.scales,
        features(history, len(history) - 1),
    )
    estimate = history[-1].close * exp(max(-1.0, min(1.0, model.blend * signal)))
    if not isfinite(estimate) or estimate <= 0:
        raise ValueError("Invalid hybrid forecast")
    return estimate
