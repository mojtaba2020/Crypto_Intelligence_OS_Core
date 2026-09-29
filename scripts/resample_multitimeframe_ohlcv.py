#!/usr/bin/env python3
"""Point-in-time-safe UTC resampling for multi-timeframe BTC research."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from calendar import monthrange
from itertools import pairwise
from datetime import UTC, datetime, timedelta
from pathlib import Path

SUPPORTED = {"1d", "1w", "1mo"}


def audit_source_rows(
    rows: list[dict[str, float]], *, source_interval_seconds: int = 3600
) -> dict[str, object]:
    """Fail closed on malformed, duplicate, or non-canonical source bars."""
    if source_interval_seconds <= 0:
        raise ValueError("source_interval_seconds must be positive")
    seen: set[int] = set()
    timestamps: list[int] = []
    for row in rows:
        ts = int(row["timestamp"])
        if ts in seen:
            raise ValueError(f"Duplicate source timestamp: {ts}")
        seen.add(ts)
        timestamps.append(ts)
        if ts % source_interval_seconds != 0:
            raise ValueError(f"Source timestamp is not interval-aligned: {ts}")
        values = {name: float(row[name]) for name in ("open", "high", "low", "close", "volume")}
        if not all(math.isfinite(value) for value in values.values()):
            raise ValueError(f"Non-finite source value at timestamp {ts}")
        if min(values["open"], values["high"], values["low"], values["close"]) <= 0:
            raise ValueError(f"OHLC values must be positive at timestamp {ts}")
        if values["volume"] < 0:
            raise ValueError(f"Volume must be non-negative at timestamp {ts}")
        if values["high"] < max(values["open"], values["close"], values["low"]):
            raise ValueError(f"High is inconsistent at timestamp {ts}")
        if values["low"] > min(values["open"], values["close"], values["high"]):
            raise ValueError(f"Low is inconsistent at timestamp {ts}")
    ordered = sorted(timestamps)
    gaps = [
        (left, right)
        for left, right in pairwise(ordered)
        if right - left != source_interval_seconds
    ]
    return {
        "rows": len(rows),
        "first_timestamp": ordered[0] if ordered else None,
        "last_timestamp": ordered[-1] if ordered else None,
        "gap_count": len(gaps),
        "continuous": not gaps,
    }


def source_data_identity(rows: list[dict[str, float]]) -> str:
    """Stable SHA-256 identity for normalized source rows."""
    normalized = [
        {
            "timestamp": int(row["timestamp"]),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row["volume"]),
        }
        for row in sorted(rows, key=lambda item: int(item["timestamp"]))
    ]
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


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
    require_complete_buckets: bool = False,
) -> list[dict[str, float]]:
    """Aggregate source-open timestamps into canonical closed UTC target bars."""
    if timeframe not in SUPPORTED:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    if source_interval_seconds <= 0:
        raise ValueError("source_interval_seconds must be positive")
    if not rows:
        return []

    audit_source_rows(rows, source_interval_seconds=source_interval_seconds)
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
        if require_complete_buckets:
            end = _bucket_end(start, timeframe)
            expected = int((end - start).total_seconds()) // source_interval_seconds
            actual_timestamps = {int(row["timestamp"]) for row in group}
            expected_timestamps = {
                key + offset * source_interval_seconds for offset in range(expected)
            }
            if actual_timestamps != expected_timestamps:
                missing = len(expected_timestamps - actual_timestamps)
                extra = len(actual_timestamps - expected_timestamps)
                raise ValueError(
                    f"Incomplete {timeframe} bucket at {key}: "
                    f"expected={expected} actual={len(group)} missing={missing} extra={extra}"
                )
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
    parser.add_argument("--allow-incomplete-buckets", action="store_true")
    args = parser.parse_args()
    rows = json.loads(args.input.read_text(encoding="utf-8"))
    source_audit = audit_source_rows(rows, source_interval_seconds=args.source_interval_seconds)
    source_audit["data_sha256"] = source_data_identity(rows)
    if not source_audit["continuous"]:
        raise ValueError(f"Source data contains {source_audit['gap_count']} interval gaps")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "source-audit.json").write_text(
        json.dumps(source_audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    for timeframe in ("1d", "1w", "1mo"):
        result = aggregate(
            rows,
            timeframe,
            as_of_timestamp=args.as_of_timestamp,
            source_interval_seconds=args.source_interval_seconds,
            require_complete_buckets=not args.allow_incomplete_buckets,
        )
        path = args.output_dir / f"btc_ohlcv_{timeframe}.json"
        path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(f"{timeframe}: {len(result)} bars -> {path}")


if __name__ == "__main__":
    main()
