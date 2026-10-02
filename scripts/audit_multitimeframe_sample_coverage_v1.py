#!/usr/bin/env python3
"""Explain exactly why real multi-timeframe forecast samples are accepted or rejected."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from multitimeframe_features_v3 import (
    WINDOWS,
    has_valid_feature_history,
    has_valid_forecast_target,
)
from multitimeframe_lab_v1 import SPECS
from multitimeframe_split_v1 import (
    chronological_split,
    minimum_total_bars_required,
    origins_for_phase,
)

SUPPORTED_FAMILIES = {"daily", "weekly", "monthly"}


def _load(path: Path) -> list[dict[str, float]]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError(f"Expected candle list in {path}")
    return rows


def _reason(candles: list[dict[str, float]], family: str, origin: int, horizon: int) -> str:
    feature_ok = has_valid_feature_history(candles, family, origin)
    target_ok = has_valid_forecast_target(candles, family, origin, horizon)
    if feature_ok and target_ok:
        return "valid"
    if not feature_ok and not target_ok:
        return "feature_and_target"
    return "feature_history" if not feature_ok else "forecast_target"


def _phase_audit(
    candles: list[dict[str, float]], family: str, horizon: int, origins: list[int]
) -> dict[str, object]:
    counts = {"valid": 0, "feature_history": 0, "forecast_target": 0, "feature_and_target": 0}
    examples: dict[str, list[dict[str, int]]] = {key: [] for key in counts if key != "valid"}
    for origin in origins:
        reason = _reason(candles, family, origin, horizon)
        counts[reason] += 1
        if reason != "valid" and len(examples[reason]) < 5:
            examples[reason].append(
                {
                    "origin_index": origin,
                    "origin_timestamp": int(candles[origin]["timestamp"]),
                }
            )
    return {"counts": counts, "examples": examples}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--exchange", default="bitstamp")
    args = parser.parse_args()

    report: dict[str, object] = {
        "status": "MULTITIMEFRAME_SAMPLE_COVERAGE_AUDIT_V1",
        "exchange": args.exchange,
        "policy": "diagnostic_only_no_model_selection_no_locked_outcome_tuning",
        "horizons": {},
    }
    horizons: dict[str, object] = report["horizons"]  # type: ignore[assignment]
    for spec in SPECS:
        if spec.family not in SUPPORTED_FAMILIES:
            continue
        candles = _load(args.data_dir / f"{args.exchange}_{spec.source_timeframe}.json")
        incomplete = [int(row["timestamp"]) for row in candles if row.get("is_complete") is False]
        try:
            split = chronological_split(len(candles), spec.minimum_history_bars, spec.horizon_bars)
        except ValueError as exc:
            horizons[spec.label] = {
                "status": "INSUFFICIENT_HISTORY",
                "reason": str(exc),
                "bars": len(candles),
                "minimum_history_bars": spec.minimum_history_bars,
                "minimum_total_bars_required": minimum_total_bars_required(
                    spec.minimum_history_bars, spec.horizon_bars
                ),
                "history_shortfall_bars": max(
                    0,
                    minimum_total_bars_required(spec.minimum_history_bars, spec.horizon_bars)
                    - len(candles),
                ),
                "longest_feature_window": max(WINDOWS[spec.family]),
                "incomplete_buckets": len(incomplete),
            }
            continue
        phases = {}
        for phase in ("validation", "locked_test"):
            origins = origins_for_phase(split, phase, spec.evaluation_step_bars)
            phases[phase] = _phase_audit(candles, spec.family, spec.horizon_bars, origins)
        horizons[spec.label] = {
            "status": "AUDITED",
            "bars": len(candles),
            "longest_feature_window": max(WINDOWS[spec.family]),
            "incomplete_buckets": len(incomplete),
            "split": split.as_dict(),
            "phases": phases,
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
