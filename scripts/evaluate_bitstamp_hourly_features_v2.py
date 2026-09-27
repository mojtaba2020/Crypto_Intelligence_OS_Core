#!/usr/bin/env python3
"""Evaluate hourly Feature V2 on validated Bitstamp long-history archive."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from attribute_hourly_candle_features_v2 import tournament
from crypto_intelligence_os.adapters.market_data.bitstamp import INSTRUMENT_ID, SOURCE_ID
from crypto_intelligence_os.adapters.market_data.historical_archive import (
    HistoricalOHLCVArchive,
    validate_hourly_continuity,
)


def run(database: Path, output: Path, *, train_min: int = 720, step: int = 24) -> dict:
    with HistoricalOHLCVArchive(database) as archive:
        archive.integrity_check()
        bars = archive.read(
            instrument_id=INSTRUMENT_ID,
            timeframe="1h",
            source_id=SOURCE_ID,
        )
    validate_hourly_continuity(bars)
    candles = [
        {
            "open": float(bar.open),
            "high": float(bar.high),
            "low": float(bar.low),
            "close": float(bar.close),
            "volume": float(bar.volume),
        }
        for bar in bars
    ]
    report = tournament(candles, train_min=train_min, step=step)
    report["data_source"] = SOURCE_ID
    report["instrument_id"] = INSTRUMENT_ID
    report["validated_bar_count"] = len(bars)
    report["train_min_hours"] = train_min
    report["walk_forward_step_hours"] = step
    report["first_open_utc"] = bars[0].open_time.isoformat()
    report["last_open_utc"] = bars[-1].open_time.isoformat()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--train-min", type=int, default=720)
    parser.add_argument("--step", type=int, default=24)
    args = parser.parse_args()
    print(json.dumps(run(args.database, args.output, train_min=args.train_min, step=args.step), indent=2))


if __name__ == "__main__":
    main()
