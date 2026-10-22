#!/usr/bin/env python3
"""Calendar-preserving moving-block bootstrap for regime-conditioned forecast losses."""

from __future__ import annotations

import math
import random
import statistics


def calendar_regime_block_bootstrap(
    model_losses: list[float],
    baseline_losses: list[float],
    selected: list[bool],
    *,
    block_length: int = 7,
    repetitions: int = 10_000,
    seed: int = 20260927,
) -> dict:
    if not (len(model_losses) == len(baseline_losses) == len(selected)):
        raise ValueError("Losses and regime mask must have equal length")
    n = len(model_losses)
    selected_count = sum(bool(x) for x in selected)
    if selected_count < 40:
        raise ValueError("Need at least 40 selected regime observations")
    if block_length < 1 or block_length > n:
        raise ValueError("Invalid block length")

    diffs = [
        baseline - model
        for model, baseline in zip(model_losses, baseline_losses, strict=True)
    ]
    observed = statistics.mean(
        diff for diff, keep in zip(diffs, selected, strict=True) if keep
    )

    # Deterministic PRNG is required for reproducible statistical bootstrap.
    rng = random.Random(seed)  # noqa: S311
    starts = list(range(n - block_length + 1))
    blocks_needed = math.ceil(n / block_length)
    means: list[float] = []
    attempts = 0
    max_attempts = repetitions * 2

    while len(means) < repetitions and attempts < max_attempts:
        attempts += 1
        sampled_indices: list[int] = []
        for _ in range(blocks_needed):
            start = rng.choice(starts)
            sampled_indices.extend(range(start, start + block_length))
        sampled_indices = sampled_indices[:n]
        selected_diffs = [
            diffs[index]
            for index in sampled_indices
            if selected[index]
        ]
        if selected_diffs:
            means.append(statistics.mean(selected_diffs))

    if len(means) != repetitions:
        raise ValueError("Unable to draw enough regime-preserving bootstrap samples")

    means.sort()
    lower = means[int(0.025 * repetitions)]
    upper = means[min(repetitions - 1, int(0.975 * repetitions))]
    probability_positive = sum(value > 0 for value in means) / repetitions
    return {
        "calendar_samples": n,
        "selected_regime_samples": selected_count,
        "mean_loss_improvement": observed,
        "ci_95": [lower, upper],
        "bootstrap_probability_improvement_positive": probability_positive,
        "block_length": block_length,
        "repetitions": repetitions,
        "bootstrap": "calendar_preserving_moving_block",
        "gate": "PASS" if lower > 0 else "FAIL",
    }
