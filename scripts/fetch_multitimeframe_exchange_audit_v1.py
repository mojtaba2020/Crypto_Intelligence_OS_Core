#!/usr/bin/env python3
"""Fetch and audit real BTC/USD hourly history from independent exchanges."""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from crypto_intelligence_os.adapters.market_data import bitfinex, bitstamp
from resample_multitimeframe_ohlcv import audit_source_rows, source_data_identity

SOURCE_INTERVAL_SECONDS = 3600
DEFAULT_START = datetime(2011, 8, 18, tzinfo=UTC)
DEFAULT_END = datetime(2026, 9, 29, tzinfo=UTC)


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamps must be timezone-aware")
    return parsed.astimezone(UTC)


def _row(bar: object) -> dict[str, float]:
    return {
        "timestamp": float(int(bar.open_time.timestamp())),
        "open": float(bar.open),
        "high": float(bar.high),
        "low": float(bar.low),
        "close": float(bar.close),
        "volume": float(bar.volume),
    }


def _fetch_range(
    fetch_page: Callable[..., tuple],
    *,
    start: datetime,
    end: datetime,
    page_hours: int,
    limit: int,
    retries: int = 4,
) -> list[dict[str, float]]:
    if start >= end:
        raise ValueError("start must be earlier than end")
    collected: dict[int, dict[str, float]] = {}
    cursor = start
    while cursor < end:
        page_end = min(end, cursor + timedelta(hours=page_hours))
        last_error: Exception | None = None
        page = None
        for attempt in range(retries):
            try:
                page = fetch_page(start=cursor, end=page_end, limit=limit)
                break
            except (OSError, TimeoutError, RuntimeError) as exc:
                last_error = exc
                if attempt + 1 < retries:
                    time.sleep(2**attempt)
        if page is None:
            raise RuntimeError(
                f"Exchange page fetch failed for {cursor.isoformat()} to {page_end.isoformat()}"
            ) from last_error
        for bar in page:
            normalized = _row(bar)
            ts = int(normalized["timestamp"])
            if not int(cursor.timestamp()) <= ts < int(page_end.timestamp()):
                continue
            previous = collected.get(ts)
            if previous is not None and previous != normalized:
                raise ValueError(f"Conflicting exchange candle at timestamp {ts}")
            collected[ts] = normalized
        cursor = page_end
    return [collected[key] for key in sorted(collected)]


def _coverage(rows: list[dict[str, float]]) -> dict[str, object]:
    if not rows:
        return {
            "observed_first_timestamp": None,
            "observed_last_timestamp": None,
            "expected_hours_within_observed_span": 0,
            "missing_hours_within_observed_span": 0,
        }
    first = int(rows[0]["timestamp"])
    last = int(rows[-1]["timestamp"])
    expected = (last - first) // SOURCE_INTERVAL_SECONDS + 1
    return {
        "observed_first_timestamp": first,
        "observed_last_timestamp": last,
        "expected_hours_within_observed_span": expected,
        "missing_hours_within_observed_span": expected - len(rows),
    }


def _write_exchange(
    name: str,
    rows: list[dict[str, float]],
    output_dir: Path,
    *,
    requested_start: datetime,
    requested_end: datetime,
) -> dict[str, object]:
    audit = audit_source_rows(rows, source_interval_seconds=SOURCE_INTERVAL_SECONDS)
    audit.update(_coverage(rows))
    audit.update(
        {
            "exchange": name,
            "requested_start": requested_start.isoformat(),
            "requested_end": requested_end.isoformat(),
            "data_sha256": source_data_identity(rows),
        }
    )
    (output_dir / f"{name}_hourly.json").write_text(
        json.dumps(rows, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    (output_dir / f"{name}_audit.json").write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default=DEFAULT_START.isoformat())
    parser.add_argument("--end", default=DEFAULT_END.isoformat())
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    start = _parse_utc(args.start)
    end = _parse_utc(args.end)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    bitstamp_rows = _fetch_range(
        bitstamp.fetch_hourly,
        start=start,
        end=end,
        page_hours=1000,
        limit=1000,
    )
    bitfinex_rows = _fetch_range(
        bitfinex.fetch_hourly,
        start=start,
        end=end,
        page_hours=9000,
        limit=9000,
    )
    audits = {
        "bitstamp": _write_exchange(
            "bitstamp", bitstamp_rows, args.output_dir, requested_start=start, requested_end=end
        ),
        "bitfinex": _write_exchange(
            "bitfinex", bitfinex_rows, args.output_dir, requested_start=start, requested_end=end
        ),
    }
    firsts = [
        int(audit["observed_first_timestamp"])
        for audit in audits.values()
        if audit["observed_first_timestamp"] is not None
    ]
    lasts = [
        int(audit["observed_last_timestamp"])
        for audit in audits.values()
        if audit["observed_last_timestamp"] is not None
    ]
    manifest = {
        "status": "REAL_EXCHANGE_DATA_AUDIT_V1",
        "requested_start": start.isoformat(),
        "requested_end": end.isoformat(),
        "exchanges": audits,
        "common_overlap_start": max(firsts) if len(firsts) == 2 else None,
        "common_overlap_end": min(lasts) if len(lasts) == 2 else None,
        "automatic_model_promotion": False,
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
