#!/usr/bin/env python3
"""Run the statistical acceptance gate for one hourly feature candidate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from paired_block_bootstrap import paired_block_bootstrap


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attribution", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--feature", default="range_mean_6h")
    parser.add_argument("--horizon", type=int, default=12)
    parser.add_argument("--block-length", type=int, default=7)
    args = parser.parse_args()

    report = json.loads(args.attribution.read_text(encoding="utf-8"))
    row = next(r for r in report["rows"] if int(r["horizon_hours"]) == args.horizon)
    candidate = row["single_feature"][args.feature]
    paired = candidate["paired_losses"]
    gate = paired_block_bootstrap(
        paired["model_losses"],
        paired["baseline_losses"],
        block_length=args.block_length,
    )
    result = {
        "status": "HOURLY_FEATURE_STATISTICAL_GATE_V3",
        "feature": args.feature,
        "horizon_hours": args.horizon,
        "point_estimate_improvement_vs_persistence_pct": candidate[
            "mape_improvement_vs_persistence_pct"
        ],
        "direction_accuracy_pct": candidate["direction_accuracy_pct"],
        "statistical_gate": gate,
        "decision": (
            "CANDIDATE_REQUIRES_MULTIPLICITY_CONTROL"
            if gate["gate"] == "PASS" and gate["one_sided_null_centered_p_value"] <= 0.05
            else "FAIL"
        ),
        "p_value_method": "null_centered_paired_moving_block_bootstrap",
        "automatic_promotion": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
