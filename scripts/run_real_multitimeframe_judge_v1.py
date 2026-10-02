#!/usr/bin/env python3
"""Run validation selection and locked OOS judge on real Bitstamp multi-timeframe data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from multitimeframe_features_v3 import is_temporally_valid_sample
from multitimeframe_judge_v1 import holm_rejections, judge_locked, select_on_validation
from multitimeframe_lab_v1 import SPECS
from multitimeframe_split_v1 import chronological_split, origins_for_phase
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
    args = parser.parse_args()

    results: dict[str, dict[str, object]] = {}
    family_p_values: dict[str, dict[str, float]] = {}
    dataset_ids: dict[str, str] = {}

    skipped: dict[str, dict[str, object]] = {}
    for spec in SPECS:
        if spec.family not in SUPPORTED_FAMILIES:
            continue
        candles = _load(args.data_dir / f"{args.exchange}_{spec.source_timeframe}.json")
        dataset_ids[spec.source_timeframe] = prepared_data_identity(candles)
        try:
            split = chronological_split(
                len(candles),
                spec.minimum_history_bars,
                spec.horizon_bars,
            )
        except ValueError as exc:
            skipped[spec.label] = {
                "family": spec.family,
                "source_timeframe": spec.source_timeframe,
                "bars": len(candles),
                "minimum_history_bars": spec.minimum_history_bars,
                "reason": str(exc),
                "status": "NOT_EVALUATED_INSUFFICIENT_HISTORY",
            }
            continue
        raw_validation_origins = origins_for_phase(
            split,
            "validation",
            spec.evaluation_step_bars,
        )
        raw_locked_origins = origins_for_phase(
            split,
            "locked_test",
            spec.evaluation_step_bars,
        )
        validation_origins = [
            origin
            for origin in raw_validation_origins
            if is_temporally_valid_sample(candles, spec.family, origin, spec.horizon_bars)
        ]
        locked_origins = [
            origin
            for origin in raw_locked_origins
            if is_temporally_valid_sample(candles, spec.family, origin, spec.horizon_bars)
        ]
        if len(validation_origins) < 8 or len(locked_origins) < 8:
            skipped[spec.label] = {
                "family": spec.family,
                "source_timeframe": spec.source_timeframe,
                "bars": len(candles),
                "minimum_history_bars": spec.minimum_history_bars,
                "raw_validation_origins": len(raw_validation_origins),
                "gap_safe_validation_origins": len(validation_origins),
                "raw_locked_origins": len(raw_locked_origins),
                "gap_safe_locked_origins": len(locked_origins),
                "gap_policy": "per_origin_feature_history_and_target_continuity_no_imputation",
                "status": "NOT_EVALUATED_GAP_SAFE_INSUFFICIENT_ORIGINS",
            }
            continue
        selected, validation_scores = select_on_validation(
            candles,
            spec.family,
            spec.horizon_bars,
            validation_origins,
        )
        locked = judge_locked(
            candles,
            spec.family,
            spec.horizon_bars,
            locked_origins,
            selected,
            spec.bootstrap_block_bars,
        )
        results[spec.label] = {
            "family": spec.family,
            "source_timeframe": spec.source_timeframe,
            "horizon_bars": spec.horizon_bars,
            "dataset_sha256": dataset_ids[spec.source_timeframe],
            "split": split.as_dict(),
            "validation_origins": len(validation_origins),
            "locked_origins": len(locked_origins),
            "gap_filtered_validation_origins": (
                len(raw_validation_origins) - len(validation_origins)
            ),
            "gap_filtered_locked_origins": len(raw_locked_origins) - len(locked_origins),
            "gap_policy": "per_origin_feature_history_and_target_continuity_no_imputation",
            "validation_selected_candidate": selected,
            "validation_scores": validation_scores,
            "locked": locked,
        }
        family_p_values.setdefault(spec.family, {})[spec.label] = float(locked["p_value"])

    for _family, p_values in family_p_values.items():
        decisions = holm_rejections(p_values)
        for label, reject in decisions.items():
            locked = results[label]["locked"]
            gate = (
                float(locked["mean_improvement"]) > 0.0
                and float(locked["ci95_low"]) > 0.0
                and reject
            )
            results[label]["holm_reject"] = reject
            results[label]["statistical_gate_pass"] = gate
            results[label]["production_promotion"] = False

    report = {
        "status": "REAL_BITSTAMP_MULTITIMEFRAME_LOCKED_JUDGE_V1",
        "exchange": args.exchange,
        "selection": "validation_only",
        "locked_test": "single_use_evaluation",
        "multiple_comparisons": "holm_within_daily_weekly_monthly_family",
        "results": results,
        "skipped": skipped,
        "automatic_model_promotion": False,
        "independent_replication_required": True,
        "prospective_confirmation_required": True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
