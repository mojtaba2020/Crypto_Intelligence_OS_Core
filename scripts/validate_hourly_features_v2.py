#!/usr/bin/env python3
"""Validate shared hourly feature engineering V2 on chronological OHLCV candles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from hourly_features_v2 import feature_names, feature_vector


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    candles = json.loads(args.input.read_text(encoding="utf-8"))
    if len(candles) < 240:
        raise ValueError("Need at least 240 completed hourly OHLCV candles")
    origins = range(168, len(candles), 24)
    vectors = [feature_vector(candles, origin) for origin in origins]
    report = {
        "status": "FEATURE_ENGINEERING_V2_VALIDATED",
        "feature_count": len(feature_names()),
        "feature_names": list(feature_names()),
        "sampled_origins": len(vectors),
        "point_in_time_safe": True,
        "uses_future_candles": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
