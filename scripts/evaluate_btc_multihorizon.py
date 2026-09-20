#!/usr/bin/env python3
"""Run comparable walk-forward BTC benchmarks across all supported daily horizons."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.evaluate_btc_hybrid import evaluate

HORIZONS = (1, 3, 7, 30, 90, 180, 365)


def plan(horizon: int) -> tuple[int, int]:
    """Choose a long holdout and a stride that limits overlap at longer horizons."""
    if horizon <= 7:
        return 1460, max(1, horizon)
    if horizon <= 30:
        return 1825, 7
    if horizon <= 90:
        return 2190, 14
    if horizon <= 180:
        return 2555, 30
    return 2920, 60


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
        rows.append(
            {
                "horizon_days": horizon,
                "holdout_days": holdout_days,
                "step_days": step,
                "test_examples": result["test_examples"],
                "first_test_origin": result["first_test_origin"],
                "last_test_origin": result["last_test_origin"],
                "metrics": metrics,
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
