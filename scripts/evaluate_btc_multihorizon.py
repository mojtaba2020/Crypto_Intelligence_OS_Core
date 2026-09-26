#!/usr/bin/env python3
"""Run comparable walk-forward BTC benchmarks across all supported daily horizons."""

from __future__ import annotations

import argparse
import json
from math import erf, sqrt
from pathlib import Path

from scripts.evaluate_btc_hybrid import evaluate

HORIZONS = (1, 3, 7, 14, 21, 30, 90, 180, 365)


def plan(horizon: int) -> tuple[int, int]:
    """Choose a long holdout and a stride that limits overlap at longer horizons."""
    # Keep every horizon, but avoid thousands of nearly identical refits.
    # The stride remains much shorter than the multi-year holdout so each
    # horizon still gets broad out-of-sample coverage across market regimes.
    if horizon <= 7:
        return 1460, 7
    if horizon <= 30:
        return 1825, 14
    if horizon <= 90:
        return 2190, 30
    if horizon <= 180:
        return 2555, 60
    return 2920, 90


def significance_gate(losses: list[dict[str, object]], model: str, horizon: int, step: int) -> dict:
    """One-sided HAC test that a model has lower mean absolute error than persistence."""
    differences = [
        float(row[f"{model}_abs_error"]) - float(row["persistence_abs_error"])
        for row in losses
    ]
    n = len(differences)
    minimum_examples = 40
    if n < 2:
        return {"status": "INSUFFICIENT_DATA", "examples": n}
    mean = sum(differences) / n
    centered = [value - mean for value in differences]
    max_lag = min(n - 1, max(1, (horizon + step - 1) // step))
    gamma0 = sum(value * value for value in centered) / n
    long_run_variance = gamma0
    for lag in range(1, max_lag + 1):
        covariance = sum(
            centered[index] * centered[index - lag] for index in range(lag, n)
        ) / n
        weight = 1 - lag / (max_lag + 1)
        long_run_variance += 2 * weight * covariance
    standard_error = sqrt(max(long_run_variance, 0.0) / n)
    z_score = mean / standard_error if standard_error > 0 else 0.0
    # One-sided normal approximation: negative loss differential favors the model.
    p_value = 0.5 * (1 + erf(z_score / sqrt(2)))
    passed = n >= minimum_examples and mean < 0 and p_value < 0.05
    return {
        "status": "PASS" if passed else "FAIL",
        "examples": n,
        "mean_absolute_error_difference_usd": mean,
        "hac_max_lag": max_lag,
        "z_score": z_score,
        "one_sided_p_value": p_value,
        "alpha": 0.05,
        "minimum_examples": minimum_examples,
    }


def run(database: Path) -> dict:
    rows = []
    for horizon in HORIZONS:
        holdout_days, step = plan(horizon)
        result = evaluate(
            database,
            horizon=horizon,
            holdout_days=holdout_days,
            step=step,
            ablation=False,
        )
        metrics = result["metrics"]
        best = min(
            metrics,
            key=lambda name: (
                metrics[name]["mae_usd"],
                metrics[name]["mape_pct"],
                name,
            ),
        )
        persistence = metrics["persistence"]["mae_usd"]
        best_mae = metrics[best]["mae_usd"]
        significance = {
            model: significance_gate(result["paired_losses"], model, horizon, step)
            for model in ("hybrid", "linear")
        }
        rows.append(
            {
                "horizon_days": horizon,
                "holdout_days": holdout_days,
                "step_days": step,
                "test_examples": result["test_examples"],
                "first_test_origin": result["first_test_origin"],
                "last_test_origin": result["last_test_origin"],
                "metrics": metrics,
                "regimes": result["regimes"],
                "significance_vs_persistence": significance,
                "lowest_mae_model_on_this_backtest": best,
                "mae_improvement_vs_persistence_pct": (
                    100 * (persistence - best_mae) / persistence if persistence else None
                ),
                "research_only": True,
            }
        )
    return {
        "status": "MULTIHORIZON_WALK_FORWARD_RESEARCH",
        "horizons_days": list(HORIZONS),
        "results": rows,
        "warning": (
            "Historical walk-forward evidence only. A backtest winner is not automatically "
            "eligible for production; prospective evidence remains required."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.database)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
