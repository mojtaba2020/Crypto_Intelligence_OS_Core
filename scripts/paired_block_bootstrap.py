#!/usr/bin/env python3
"""Paired moving-block bootstrap gate for forecast loss improvements."""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from pathlib import Path


def paired_block_bootstrap(
    model_losses: list[float],
    baseline_losses: list[float],
    *,
    block_length: int = 7,
    repetitions: int = 10_000,
    seed: int = 20260927,
) -> dict:
    if len(model_losses) != len(baseline_losses) or len(model_losses) < 40:
        raise ValueError("Need at least 40 paired losses of equal length")
    if block_length < 1 or block_length > len(model_losses):
        raise ValueError("Invalid block length")
    diffs = [b - m for m, b in zip(model_losses, baseline_losses, strict=True)]
    n = len(diffs)
    observed = statistics.mean(diffs)
    # Deterministic PRNG is required for reproducible statistical bootstrap.
    rng = random.Random(seed)  # noqa: S311
    starts = list(range(n - block_length + 1))
    means: list[float] = []
    blocks_needed = math.ceil(n / block_length)
    for _ in range(repetitions):
        sample: list[float] = []
        for _ in range(blocks_needed):
            start = rng.choice(starts)
            sample.extend(diffs[start : start + block_length])
        means.append(statistics.mean(sample[:n]))
    means.sort()
    lower = means[int(0.025 * repetitions)]
    upper = means[min(repetitions - 1, int(0.975 * repetitions))]
    probability_positive = sum(x > 0 for x in means) / repetitions
    null_diffs = [x - observed for x in diffs]
    null_means: list[float] = []
    for _ in range(repetitions):
        sample: list[float] = []
        for _ in range(blocks_needed):
            start = rng.choice(starts)
            sample.extend(null_diffs[start : start + block_length])
        null_means.append(statistics.mean(sample[:n]))
    extreme = sum(x >= observed for x in null_means)
    one_sided_null_p_value = (extreme + 1) / (repetitions + 1)
    return {
        "paired_samples": n,
        "mean_loss_improvement": observed,
        "ci_95": [lower, upper],
        "bootstrap_probability_improvement_positive": probability_positive,
        "one_sided_null_centered_p_value": one_sided_null_p_value,
        "null_hypothesis": "mean_loss_improvement_lte_zero",
        "block_length": block_length,
        "repetitions": repetitions,
        "gate": "PASS" if lower > 0 else "FAIL",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--block-length", type=int, default=7)
    parser.add_argument("--repetitions", type=int, default=10_000)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    report = paired_block_bootstrap(
        [float(x) for x in payload["model_losses"]],
        [float(x) for x in payload["baseline_losses"]],
        block_length=args.block_length,
        repetitions=args.repetitions,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "
", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
