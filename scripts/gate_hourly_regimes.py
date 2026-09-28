#!/usr/bin/env python3
"""Evaluate paired forecast losses inside point-in-time market regimes."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from calendar_regime_block_bootstrap import calendar_regime_block_bootstrap
from hourly_regime_v1 import classify_regime


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candles", required=True, type=Path)
    parser.add_argument("--paired", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--min-samples", type=int, default=40)
    parser.add_argument("--block-length", type=int, default=7)
    args = parser.parse_args()

    candles = json.loads(args.candles.read_text(encoding="utf-8"))
    payload = json.loads(args.paired.read_text(encoding="utf-8"))
    origins = [int(x) for x in payload["origins"]]
    model = [float(x) for x in payload["model_losses"]]
    baseline = [float(x) for x in payload["baseline_losses"]]
    if not (len(origins) == len(model) == len(baseline)):
        raise ValueError("Paired origins/losses must have equal length")

    regimes = [classify_regime(candles, origin) for origin in origins]

    rows = []
    for regime in sorted(set(regimes)):
        selected = [value == regime for value in regimes]
        selected_model = [
            loss for loss, keep in zip(model, selected, strict=True) if keep
        ]
        selected_baseline = [
            loss for loss, keep in zip(baseline, selected, strict=True) if keep
        ]
        n = len(selected_model)
        model_mape = 100 * statistics.mean(selected_model)
        baseline_mape = 100 * statistics.mean(selected_baseline)
        row = {
            "regime": regime,
            "samples": n,
            "model_mape_pct": model_mape,
            "persistence_mape_pct": baseline_mape,
            "mape_improvement_vs_persistence_pct": (
                100 * (baseline_mape - model_mape) / baseline_mape
                if baseline_mape
                else 0.0
            ),
        }
        if n >= args.min_samples:
            row["statistical_gate"] = calendar_regime_block_bootstrap(
                model,
                baseline,
                selected,
                block_length=min(args.block_length, len(model)),
            )
            raw_gate = row["statistical_gate"]["gate"]
            row["raw_gate"] = raw_gate
            row["decision"] = (
                "EXPLORATORY_PASS_REQUIRES_CONFIRMATION"
                if raw_gate == "PASS"
                else "FAIL"
            )
        else:
            row["decision"] = "INSUFFICIENT_SAMPLES"
        rows.append(row)

    eligible = [row for row in rows if row.get("statistical_gate")]
    ordered = sorted(eligible, key=lambda row: (row["statistical_gate"]["one_sided_null_centered_p_value"], row["regime"]))
    holm_open = True
    for rank, row in enumerate(ordered, start=1):
        gate = row["statistical_gate"]
        p_value = gate["one_sided_null_centered_p_value"]
        threshold = 0.05 / (len(ordered) - rank + 1)
        reject = holm_open and p_value <= threshold
        if not reject:
            holm_open = False
        gate["holm_rank"] = rank
        gate["holm_threshold"] = threshold
        gate["holm_reject"] = reject
        row["decision"] = (
            "EXPLORATORY_PASS_REQUIRES_INDEPENDENT_CONFIRMATION"
            if reject and gate["gate"] == "PASS"
            else "FAIL"
        )

    result = {
        "status": "HOURLY_REGIME_GATE_V3",
        "regime_definition": "24h trend band x trailing point-in-time 24h volatility median",
        "research_status": "EXPLORATORY",
        "bootstrap": "null_centered_calendar_preserving_moving_block",
        "multiple_comparison_method": "holm_bonferroni_over_observed_regimes",
        "familywise_alpha": 0.05,
        "automatic_promotion": False,
        "confirmation_requirements": [
            "independent confirmation after Holm-controlled exploratory discovery",
            "independent time period or independent exchange",
            "predeclared confirmatory hypothesis",
        ],
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
