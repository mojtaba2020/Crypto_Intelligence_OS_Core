#!/usr/bin/env python3
"""Development/validation-only runner for Challenger V3 classical models."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from multitimeframe_lab_v1 import SPECS
from multitimeframe_split_v1 import chronological_split
from multitimeframe_tournament_v2 import CANDIDATES, evaluate
from resample_multitimeframe_ohlcv import prepared_data_identity

SUPPORTED_FAMILIES = {"daily", "weekly", "monthly"}


def _load(path: Path) -> list[dict[str, float]]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError(f"Expected candle list in {path}")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--exchange", default="bitstamp")
    valid_horizons = tuple(spec.label for spec in SPECS if spec.family in SUPPORTED_FAMILIES)
    parser.add_argument(
        "--horizon",
        default=None,
        choices=valid_horizons,
        help="Evaluate only one predeclared horizon.",
    )
    args = parser.parse_args()

    results: dict[str, dict[str, object]] = {}
    skipped: dict[str, dict[str, object]] = {}

    for spec in SPECS:
        if args.horizon is not None and spec.label != args.horizon:
            continue
        if spec.family not in SUPPORTED_FAMILIES:
            continue

        candles = _load(args.data_dir / f"{args.exchange}_{spec.source_timeframe}.json")
        dataset_sha = prepared_data_identity(candles)

        try:
            split = chronological_split(
                len(candles),
                spec.minimum_history_bars,
                spec.horizon_bars,
            )
        except ValueError as exc:
            skipped[spec.label] = {
                "status": "NOT_EVALUATED_INSUFFICIENT_HISTORY",
                "reason": str(exc),
                "bars": len(candles),
            }
            continue

        # Locked-test candles are physically excluded.
        validation_view = candles[: split.validation_end]

        started = time.perf_counter()
        print('[V3] START ' + spec.label, flush=True)
        try:
            metrics = evaluate(
                validation_view,
                spec.family,
                spec.horizon_bars,
                spec.minimum_history_bars,
                spec.evaluation_step_bars,
            )
        except ValueError as exc:
            skipped[spec.label] = {
                "status": "NOT_EVALUATED_INSUFFICIENT_GAP_SAFE_VALIDATION",
                "reason": str(exc),
                "validation_boundary": split.validation_end,
            }
            continue

        elapsed = time.perf_counter() - started
        print('[V3] DONE ' + spec.label + ' seconds=' + format(elapsed, '.2f'), flush=True)
        candidate_metrics = metrics["candidates"]
        rank = {name: index for index, name in enumerate(CANDIDATES)}
        selected = min(
            CANDIDATES,
            key=lambda name: (
                float(candidate_metrics[name]["mape"]),
                rank[name],
            ),
        )

        results[spec.label] = {
            "family": spec.family,
            "source_timeframe": spec.source_timeframe,
            "horizon_bars": spec.horizon_bars,
            "dataset_sha256": dataset_sha,
            "data_role": "development_validation_only",
            "locked_test_access": False,
            "validation_boundary": split.validation_end,
            "selected_candidate": selected,
            "runtime_seconds": round(elapsed, 3),
            "metrics": metrics,
        }

    report = {
        "status": "CHALLENGER_V3_CLASSICAL_DEVELOPMENT_VALIDATION_ONLY",
        "exchange": args.exchange,
        "candidate_order": list(CANDIDATES),
        "results": results,
        "skipped": skipped,
        "fresh_locked_oos_access": False,
        "v2_locked_oos_used_for_tuning": False,
        "production_promotion": False,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
