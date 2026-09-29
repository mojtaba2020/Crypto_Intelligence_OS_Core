#!/usr/bin/env python3
"""Validation-only selection and locked OOS statistical judge."""

from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass

from scripts.multitimeframe_features_v3 import WINDOWS, feature_vector
from scripts.multitimeframe_tournament_v1 import CANDIDATES, _fit_candidate, _known_training_origins


@dataclass(frozen=True)
class CandidateResult:
    name: str
    losses: tuple[float, ...]
    baseline_losses: tuple[float, ...]

    @property
    def mean_loss(self) -> float:
        return statistics.mean(self.losses)

    @property
    def mean_improvement(self) -> float:
        return statistics.mean(
            base - model for base, model in zip(self.baseline_losses, self.losses, strict=True)
        )


def _evaluate_candidate(
    candles: list[dict[str, float]],
    family: str,
    horizon: int,
    origins: list[int],
    candidate: str,
) -> CandidateResult:
    longest = max(WINDOWS[family])
    losses: list[float] = []
    baseline_losses: list[float] = []
    for origin in origins:
        train_origins = _known_training_origins(longest, origin, horizon)
        if not train_origins:
            raise ValueError("No known training labels at evaluation origin")
        x = [feature_vector(candles, i, family) for i in train_origins]
        y = [
            math.log(float(candles[i + horizon]["close"]) / float(candles[i]["close"]))
            for i in train_origins
        ]
        predictor = _fit_candidate(candidate, x, y)
        row = feature_vector(candles, origin, family)
        predicted_return = (
            float(predictor(row)) if candidate == "ridge" else float(predictor([row])[0])
        )
        current = float(candles[origin]["close"])
        actual = float(candles[origin + horizon]["close"])
        predicted = current * math.exp(predicted_return)
        losses.append(abs(predicted - actual) / actual)
        baseline_losses.append(abs(current - actual) / actual)
    return CandidateResult(candidate, tuple(losses), tuple(baseline_losses))


def select_on_validation(
    candles: list[dict[str, float]],
    family: str,
    horizon: int,
    validation_origins: list[int],
) -> tuple[str, dict[str, float]]:
    """Select candidate using validation origins only."""
    if not validation_origins:
        raise ValueError("Validation origins cannot be empty")
    results = {
        name: _evaluate_candidate(candles, family, horizon, validation_origins, name)
        for name in CANDIDATES
    }
    selected = min(results, key=lambda name: results[name].mean_loss)
    return selected, {name: result.mean_loss for name, result in results.items()}


def null_centered_moving_block_bootstrap(
    improvements: list[float],
    block_size: int,
    draws: int = 4000,
    seed: int = 20260929,
) -> dict[str, float]:
    """One-sided paired test of H0 mean improvement <= 0 with a null-centered MBB."""
    if len(improvements) < 8:
        raise ValueError("Too few paired losses for bootstrap")
    if block_size <= 0 or block_size > len(improvements):
        raise ValueError("Invalid bootstrap block size")
    observed = statistics.mean(improvements)
    centered = [value - observed for value in improvements]
    rng = random.Random(seed)  # noqa: S311 -- deterministic statistical bootstrap
    n = len(centered)
    starts = list(range(0, n - block_size + 1))
    boot_means: list[float] = []
    for _ in range(draws):
        sample: list[float] = []
        while len(sample) < n:
            start = rng.choice(starts)
            sample.extend(centered[start : start + block_size])
        boot_means.append(statistics.mean(sample[:n]))
    p_value = (1 + sum(value >= observed for value in boot_means)) / (draws + 1)
    ordered = sorted(boot_means)
    low = observed - ordered[int(0.975 * (draws - 1))]
    high = observed - ordered[int(0.025 * (draws - 1))]
    return {
        "mean_improvement": observed,
        "ci95_low": low,
        "ci95_high": high,
        "p_value": p_value,
    }


def holm_rejections(p_values: dict[str, float], alpha: float = 0.05) -> dict[str, bool]:
    """Holm step-down rejection decisions for one declared comparison family."""
    if not p_values:
        return {}
    ordered = sorted(p_values.items(), key=lambda item: item[1])
    decisions = {name: False for name in p_values}
    still_rejecting = True
    m = len(ordered)
    for rank, (name, p_value) in enumerate(ordered):
        threshold = alpha / (m - rank)
        reject = still_rejecting and p_value <= threshold
        decisions[name] = reject
        if not reject:
            still_rejecting = False
    return decisions


def judge_locked(
    candles: list[dict[str, float]],
    family: str,
    horizon: int,
    locked_origins: list[int],
    selected_candidate: str,
    block_size: int,
) -> dict[str, object]:
    """Evaluate the frozen validation-selected challenger on locked OOS only."""
    if selected_candidate not in CANDIDATES:
        raise ValueError("Selected candidate is not declared")
    if not locked_origins:
        raise ValueError("Locked origins cannot be empty")
    result = _evaluate_candidate(candles, family, horizon, locked_origins, selected_candidate)
    improvements = [
        base - model for base, model in zip(result.baseline_losses, result.losses, strict=True)
    ]
    stats = null_centered_moving_block_bootstrap(improvements, block_size)
    return {
        "selected_candidate": selected_candidate,
        "samples": len(locked_origins),
        "challenger_mape": result.mean_loss,
        "persistence_mape": statistics.mean(result.baseline_losses),
        **stats,
        "production_promotion": False,
    }
