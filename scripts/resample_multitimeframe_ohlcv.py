#!/usr/bin/env python3
"""Point-in-time-safe UTC resampling for multi-timeframe BTC research."""

from __future__ import annotations

import argparse
import json
from calendar import monthrange
from datetime import UTC, datetime, timedelta
from pathlib import Path

SUPPORTED = {"1d", "1w", "1mo"}


def _bucket_start(ts: int, timeframe: str) -> datetime:
    dt = datetime.fromtimestamp(ts, UTC)
    if timeframe == "1d":
        return datetime(dt.year, dt.month, dt.day, tzinfo=UTC)
    if timeframe == "1w":
        day = datetime(dt.year, dt.month, dt.day, tzinfo=UTC)
        return day - timedelta(days=day.weekday())
    if timeframe == "1mo":
        return datetime(dt.year, dt.month, 1, tzinfo=UTC)
    raise ValueError(f"Unsupported timeframe: {timeframe}")


def _bucket_end(start: datetime, timeframe: str) -> datetime:
    if timeframe == "1d":
        return start + timedelta(days=1)
    if timeframe == "1w":
        return start + timedelta(days=7)
    if timeframe == "1mo":
        return start + timedelta(days=monthrange(start.year, start.month)[1])
    raise ValueError(f"Unsupported timeframe: {timeframe}")


def aggregate(
    rows: list[dict[str, float]],
    timeframe: str,
    *,
    as_of_timestamp: int | None = None,
    source_interval_seconds: int = 3600,
) -> list[dict[str, float]]:
    """Aggregate source-open timestamps into canonical closed UTC target bars."""
    if timeframe not in SUPPORTED:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    if source_interval_seconds <= 0:
        raise ValueError("source_interval_seconds must be positive")
    if not rows:
        return []

    ordered = sorted(rows, key=lambda row: int(row["timestamp"]))
    buckets: dict[int, list[dict[str, float]]] = {}
    for row in ordered:
        ts = int(row["timestamp"])
        if as_of_timestamp is not None and ts + source_interval_seconds > as_of_timestamp:
            continue
        start = _bucket_start(ts, timeframe)
        key = int(start.timestamp())
        buckets.setdefault(key, []).append(row)

    output: list[dict[str, float]] = []
    for key in sorted(buckets):
        start = datetime.fromtimestamp(key, UTC)
        if as_of_timestamp is not None:
            end_ts = int(_bucket_end(start, timeframe).timestamp())
            if end_ts > as_of_timestamp:
                continue
        group = buckets[key]
        first, last = group[0], group[-1]
        output.append(
            {
                "timestamp": key,
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
    parser.add_argument("--as-of-timestamp", type=int, required=True)
    parser.add_argument("--source-interval-seconds", type=int, default=3600)
    args = parser.parse_args()
    rows = json.loads(args.input.read_text(encoding="utf-8"))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for timeframe in ("1d", "1w", "1mo"):
        result = aggregate(
            rows,
            timeframe,
            as_of_timestamp=args.as_of_timestamp,
            source_interval_seconds=args.source_interval_seconds,
        )
        path = args.output_dir / f"btc_ohlcv_{timeframe}.json"
        path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(f"{timeframe}: {len(result)} bars -> {path}")


if __name__ == "__main__":
    main()
