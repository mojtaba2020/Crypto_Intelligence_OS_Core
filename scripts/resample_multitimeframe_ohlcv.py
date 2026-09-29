#!/usr/bin/env python3
"""Point-in-time-safe UTC resampling for multi-timeframe BTC research."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

SECONDS = {"1d": 86400, "1w": 604800, "1mo": 0}


def _month_key(ts: int) -> tuple[int, int]:
    dt = datetime.fromtimestamp(ts, UTC)
    return dt.year, dt.month


def _bucket_key(ts: int, timeframe: str) -> int | tuple[int, int]:
    if timeframe == "1mo":
        return _month_key(ts)
    seconds = SECONDS[timeframe]
    return ts // seconds


def aggregate(rows: list[dict[str, float]], timeframe: str) -> list[dict[str, float]]:
    if timeframe not in SECONDS:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    if not rows:
        return []
    ordered = sorted(rows, key=lambda row: int(row["timestamp"]))
    buckets: dict[int | tuple[int, int], list[dict[str, float]]] = {}
    for row in ordered:
        ts = int(row["timestamp"])
        buckets.setdefault(_bucket_key(ts, timeframe), []).append(row)

    output = []
    for group in buckets.values():
        first, last = group[0], group[-1]
        output.append(
            {
                "timestamp": int(first["timestamp"]),
                "open": float(first["open"]),
                "high": max(float(row["high"]) for row in group),
                "low": min(float(row["low"]) for row in group),
                "close": float(last["close"]),
                "volume": sum(float(row["volume"]) for row in group),
                "source_bars": len(group),
            }
        )
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    rows = json.loads(args.input.read_text(encoding="utf-8"))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for timeframe in ("1d", "1w", "1mo"):
        result = aggregate(rows, timeframe)
        path = args.output_dir / f"btc_ohlcv_{timeframe}.json"
        path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(f"{timeframe}: {len(result)} bars -> {path}")


if __name__ == "__main__":
    main()
