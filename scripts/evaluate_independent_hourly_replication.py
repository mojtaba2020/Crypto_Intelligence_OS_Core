#!/usr/bin/env python3
"""Evaluate locked hourly model families on an independent exchange archive."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .hourly_live_inference import predict
    from .paired_block_bootstrap import paired_block_bootstrap
except ImportError:
    from hourly_live_inference import predict
    from paired_block_bootstrap import paired_block_bootstrap

from crypto_intelligence_os.adapters.market_data.historical_archive import (
    HistoricalOHLCVArchive,
    validate_hourly_continuity,
)

HORIZONS = (1, 2, 3, 4, 12)


def evaluate(
    database: Path,
    source: str,
    instrument: str,
    model: str,
    step: int = 24,
) -> dict:
    with HistoricalOHLCVArchive(database) as archive:
        bars = archive.read(
            instrument_id=instrument,
            timeframe="1h",
            source_id=source,
        )
    validate_hourly_continuity(bars)
    closes = [float(bar.close) for bar in bars]
    rows = []
    for horizon in HORIZONS:
        model_losses = []
        baseline_losses = []
        for origin in range(240, len(closes) - horizon, step):
            history = closes[: origin + 1]
            prediction = predict(model, history, horizon)
            actual = closes[origin + horizon]
            current = closes[origin]
            model_losses.append(abs(prediction - actual) / actual)
            baseline_losses.append(abs(current - actual) / actual)
        if len(model_losses) < 40:
            raise ValueError("Independent replication requires >=40 samples per horizon")
        gate = paired_block_bootstrap(
            model_losses,
            baseline_losses,
            block_length=min(7, len(model_losses)),
        )
        rows.append(
            {
                "horizon_hours": horizon,
                "samples": len(model_losses),
                "model": model,
                "model_mape_pct": 100 * sum(model_losses) / len(model_losses),
                "persistence_mape_pct": (100 * sum(baseline_losses) / len(baseline_losses)),
                "statistical_gate": gate,
            }
        )
    ordered = sorted(
        rows,
        key=lambda row: (
            row["statistical_gate"]["one_sided_null_centered_p_value"],
            row["horizon_hours"],
        ),
    )
    gate_open = True
    for rank, row in enumerate(ordered, 1):
        gate = row["statistical_gate"]
        threshold = 0.05 / (len(ordered) - rank + 1)
        reject = gate_open and gate["one_sided_null_centered_p_value"] <= threshold
        if not reject:
            gate_open = False
        gate.update(
            {
                "holm_rank": rank,
                "holm_threshold": threshold,
                "holm_reject": reject,
            }
        )
        row["replication_decision"] = (
            "REPLICATED_RESEARCH_EDGE" if reject and gate["gate"] == "PASS" else "NOT_REPLICATED"
        )
    return {
        "status": "INDEPENDENT_EXCHANGE_REPLICATION_V1",
        "source_id": source,
        "instrument_id": instrument,
        "model": model,
        "familywise_alpha": 0.05,
        "multiple_comparison_method": "holm_bonferroni_5_horizons",
        "automatic_promotion": False,
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--instrument", required=True)
    parser.add_argument(
        "--model",
        choices=["ridge", "extra_trees", "boosting"],
        required=True,
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.database, args.source, args.instrument, args.model)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
