#!/usr/bin/env python3
"""Fail-closed hourly Champion/Challenger judge.

Selection uses validation losses only. The locked test is consulted only after
one challenger has been selected for each horizon.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path

from paired_block_bootstrap import paired_block_bootstrap

HORIZONS = (1, 2, 3, 4, 12)
CANDIDATES = ("ridge", "extra_trees", "boosting")
BENCHMARK = "persistence"
MIN_LOCKED_SAMPLES = 40
BOOTSTRAP_REPETITIONS = 10_000
BOOTSTRAP_SEED = 20260927


def _mape(losses: list[float]) -> float:
    if not losses:
        raise ValueError("Empty loss sequence")
    if any(not math.isfinite(x) or x < 0 for x in losses):
        raise ValueError("Losses must be finite and non-negative")
    return 100.0 * statistics.mean(losses)


def _validate_payload(payload: dict) -> None:
    if tuple(payload.get("horizons_hours", ())) != HORIZONS:
        raise ValueError("Hourly judge requires the locked horizon set")
    if tuple(payload.get("candidates", ())) != CANDIDATES:
        raise ValueError("Hourly judge requires the locked candidate set")
    if payload.get("benchmark") != BENCHMARK:
        raise ValueError("Hourly judge requires persistence benchmark")
    if payload.get("validation_end_origin") is None:
        raise ValueError("Missing validation boundary")
    if payload.get("locked_test_start_origin") is None:
        raise ValueError("Missing locked-test boundary")
    if int(payload["validation_end_origin"]) >= int(payload["locked_test_start_origin"]):
        raise ValueError("Validation and locked test must be chronologically separated")


def judge(payload: dict) -> dict:
    _validate_payload(payload)
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise ValueError("Missing point-in-time loss rows")

    results = []
    for horizon in HORIZONS:
        horizon_rows = [row for row in rows if int(row["horizon_hours"]) == horizon]
        validation = [row for row in horizon_rows if row["split"] == "validation"]
        locked = [row for row in horizon_rows if row["split"] == "locked_test"]
        if not validation or not locked:
            raise ValueError(f"Missing validation or locked-test rows for {horizon}h")

        validation_scores = {
            model: _mape([float(row["losses"][model]) for row in validation])
            for model in CANDIDATES
        }
        selected = min(CANDIDATES, key=lambda model: (validation_scores[model], model))

        selected_losses = [float(row["losses"][selected]) for row in locked]
        baseline_losses = [float(row["losses"][BENCHMARK]) for row in locked]
        locked_samples = len(selected_losses)
        selected_mape = _mape(selected_losses)
        baseline_mape = _mape(baseline_losses)

        if locked_samples < MIN_LOCKED_SAMPLES:
            statistical_gate = None
            decision = "INSUFFICIENT_LOCKED_SAMPLES"
        else:
            block_length = max(1, math.ceil(horizon / 24))
            statistical_gate = paired_block_bootstrap(
                selected_losses,
                baseline_losses,
                block_length=block_length,
                repetitions=BOOTSTRAP_REPETITIONS,
                seed=BOOTSTRAP_SEED,
            )
            decision = (
                "CHALLENGER_ELIGIBLE_FOR_FURTHER_VALIDATION"
                if statistical_gate["gate"] == "PASS"
                and selected_mape < baseline_mape
                else "KEEP_PERSISTENCE_CHAMPION"
            )

        results.append(
            {
                "horizon_hours": horizon,
                "selected_on_validation": selected,
                "validation_mape_pct": validation_scores,
                "locked_test_samples": locked_samples,
                "selected_locked_mape_pct": selected_mape,
                "persistence_locked_mape_pct": baseline_mape,
                "statistical_gate": statistical_gate,
                "decision": decision,
                "production_promotion": False,
            }
        )

    return {
        "status": "HOURLY_CHAMPION_CHALLENGER_RESEARCH_V1",
        "selection_rule": "lowest_validation_mape_then_name",
        "locked_test_used_for_selection": False,
        "automatic_production_promotion": False,
        "bootstrap_repetitions": BOOTSTRAP_REPETITIONS,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    report = judge(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
