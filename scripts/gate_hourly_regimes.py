#!/usr/bin/env python3
"""Evaluate paired forecast losses inside point-in-time market regimes."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from hourly_regime_v1 import classify_regime
from paired_block_bootstrap import paired_block_bootstrap


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

    groups: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: {"model": [], "baseline": []}
    )
    for origin, m, b in zip(origins, model, baseline, strict=True):
        regime = classify_regime(candles, origin)
        groups[regime]["model"].append(m)
        groups[regime]["baseline"].append(b)

    rows = []
    for regime, losses in sorted(groups.items()):
        n = len(losses["model"])
        row = {"regime": regime, "samples": n}
        if n >= args.min_samples:
            row["statistical_gate"] = paired_block_bootstrap(
                losses["model"],
                losses["baseline"],
                block_length=min(args.block_length, n),
            )
            row["decision"] = row["statistical_gate"]["gate"]
        else:
            row["decision"] = "INSUFFICIENT_SAMPLES"
        rows.append(row)

    result = {
        "status": "HOURLY_REGIME_GATE_V1",
        "regime_definition": "24h trend band x trailing point-in-time 24h volatility median",
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
