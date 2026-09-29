#!/usr/bin/env python3
"""Locked multi-timeframe research contract for Crypto Intelligence OS."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class HorizonSpec:
    label: str
    source_timeframe: str
    horizon_bars: int
    family: str
    promotion_eligible: bool
    minimum_history_bars: int
    evaluation_step_bars: int
    bootstrap_block_bars: int


SPECS: tuple[HorizonSpec, ...] = (
    HorizonSpec("1h", "1h", 1, "hourly", True, 2200, 24, 7),
    HorizonSpec("2h", "1h", 2, "hourly", True, 2200, 24, 7),
    HorizonSpec("3h", "1h", 3, "hourly", True, 2200, 24, 7),
    HorizonSpec("4h", "1h", 4, "hourly", True, 2200, 24, 7),
    HorizonSpec("12h", "1h", 12, "hourly", True, 2200, 24, 7),
    HorizonSpec("1d", "1d", 1, "daily", True, 1460, 7, 14),
    HorizonSpec("2d", "1d", 2, "daily", True, 1460, 7, 14),
    HorizonSpec("3d", "1d", 3, "daily", True, 1460, 7, 14),
    HorizonSpec("1w", "1w", 1, "weekly", True, 260, 1, 8),
    HorizonSpec("2w", "1w", 2, "weekly", True, 260, 1, 8),
    HorizonSpec("3w", "1w", 3, "weekly", True, 260, 1, 8),
    HorizonSpec("1mo", "1mo", 1, "monthly", True, 120, 1, 4),
    HorizonSpec("3mo", "1mo", 3, "monthly", True, 120, 1, 4),
    HorizonSpec("2y", "1mo", 24, "macro_cycle", False, 120, 1, 12),
    HorizonSpec("3y", "1mo", 36, "macro_cycle", False, 120, 1, 12),
    HorizonSpec("4y", "1mo", 48, "macro_cycle", False, 120, 1, 12),
    HorizonSpec("5y", "1mo", 60, "macro_cycle", False, 120, 1, 12),
    HorizonSpec("6y", "1mo", 72, "macro_cycle", False, 120, 1, 12),
    HorizonSpec("7y", "1mo", 84, "macro_cycle", False, 120, 1, 12),
    HorizonSpec("8y", "1mo", 96, "macro_cycle", False, 120, 1, 12),
)


def validate_contract(specs: tuple[HorizonSpec, ...] = SPECS) -> None:
    labels = [spec.label for spec in specs]
    if len(labels) != len(set(labels)):
        raise ValueError("Duplicate horizon labels")
    for spec in specs:
        if (
            min(
                spec.horizon_bars,
                spec.minimum_history_bars,
                spec.evaluation_step_bars,
                spec.bootstrap_block_bars,
            )
            <= 0
        ):
            raise ValueError(f"Non-positive research parameter for {spec.label}")
        if spec.family == "macro_cycle" and spec.promotion_eligible:
            raise ValueError("Sparse multi-year cycle horizons cannot auto-promote")


def manifest() -> dict[str, object]:
    validate_contract()
    return {
        "status": "MULTITIMEFRAME_RESEARCH_CONTRACT_V1",
        "selection_policy": "validation_only_then_locked_out_of_sample_judge",
        "locked_test_reuse": "forbidden_for_feature_or_hyperparameter_selection",
        "statistical_policy": {
            "paired_test": "null_centered_moving_block_bootstrap",
            "multiple_comparisons": "holm_bonferroni_within_declared_family",
            "automatic_promotion": False,
            "independent_exchange_replication_required": True,
            "prospective_confirmation_required": True,
        },
        "macro_cycle_policy": {
            "mode": "descriptive_and_hypothesis_generation_only",
            "reason": (
                "BTC history contains too few independent multi-year cycles for reliable "
                "promotion-grade inference"
            ),
        },
        "horizons": [asdict(spec) for spec in SPECS],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = manifest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
