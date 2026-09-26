#!/usr/bin/env python3
"""Validated long-history BTC OHLCV data layer for research workflows."""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import UTC, datetime
from pathlib import Path

REQUIRED = ("timestamp", "open", "high", "low", "close", "volume")
HOUR_SECONDS = 3600


def load_csv(path: Path) -> list[dict[str, float | int]]:
    rows: list[dict[str, float | int]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = set(REQUIRED) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"Missing CSV columns: {sorted(missing)}")
        for raw in reader:
            rows.append(
                {
                    "timestamp": int(float(raw["timestamp"])),
                    "open": float(raw["open"]),
                    "high": float(raw["high"]),
                    "low": float(raw["low"]),
                    "close": float(raw["close"]),
                    "volume": float(raw["volume"]),
                }
            )
    return rows


def validate(
    rows: list[dict[str, float | int]],
    *,
    now_timestamp: int | None = None,
    require_hourly: bool = True,
) -> dict:
    if not rows:
        raise ValueError("No candles supplied")
    ordered = sorted(rows, key=lambda row: int(row["timestamp"]))
    timestamps = [int(row["timestamp"]) for row in ordered]
    duplicates = len(timestamps) - len(set(timestamps))
    gaps = [
        {"after": left, "before": right, "seconds": right - left}
        for left, right in zip(timestamps, timestamps[1:], strict=False)
        if right - left != HOUR_SECONDS
    ]

    for row in ordered:
        values = [float(row[key]) for key in ("open", "high", "low", "close", "volume")]
        if any(not math.isfinite(value) for value in values):
            raise ValueError("Non-finite OHLCV value")
        if min(values[:4]) <= 0 or values[4] < 0:
            raise ValueError("Invalid OHLCV sign")
        if float(row["high"]) < max(float(row["open"]), float(row["close"]), float(row["low"])):
            raise ValueError("High price violates OHLC ordering")
        if float(row["low"]) > min(float(row["open"]), float(row["close"]), float(row["high"])):
            raise ValueError("Low price violates OHLC ordering")

    now = now_timestamp or int(datetime.now(UTC).timestamp())
    current_hour = now // HOUR_SECONDS * HOUR_SECONDS
    incomplete = [ts for ts in timestamps if ts >= current_hour]
    if duplicates:
        raise ValueError(f"Duplicate timestamps: {duplicates}")
    if incomplete:
        raise ValueError(f"Found {len(incomplete)} incomplete/future candles")
    if require_hourly and gaps:
        raise ValueError(f"Non-hourly gaps found: {len(gaps)}")

    return {
        "status": "LONG_HISTORY_DATA_VALIDATED",
        "candle_count": len(ordered),
        "start_timestamp": timestamps[0],
        "start_utc": datetime.fromtimestamp(timestamps[0], UTC).isoformat(),
        "end_timestamp": timestamps[-1],
        "end_utc": datetime.fromtimestamp(timestamps[-1], UTC).isoformat(),
        "duplicate_timestamps": duplicates,
        "gap_count": len(gaps),
        "hourly_contiguous": not gaps,
        "completed_candles_only": not incomplete,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-data", type=Path, required=True)
    parser.add_argument("--output-report", type=Path, required=True)
    args = parser.parse_args()

    rows = load_csv(args.input)
    report = validate(rows)
    ordered = sorted(rows, key=lambda row: int(row["timestamp"]))
    args.output_data.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_data.write_text(json.dumps(ordered, indent=2) + "\n", encoding="utf-8")
    args.output_report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
