#!/usr/bin/env python3
"""Backfill validated Bitfinex BTC/USD hourly history into the immutable research archive."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from crypto_intelligence_os.adapters.market_data.bitfinex import (
    INSTRUMENT_ID,
    SOURCE_ID,
    fetch_hourly,
)
from crypto_intelligence_os.adapters.market_data.historical_archive import (
    HistoricalOHLCVArchive,
    canonical_bar_fingerprint,
    validate_hourly_continuity,
)


def utc_date(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    aware = parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed
    return aware.astimezone(UTC)


def run(*, start: datetime, end: datetime, database: Path, report_path: Path) -> dict:
    if start >= end:
        raise ValueError("start must be earlier than end")
    collected = {}
    cursor = start
    while cursor < end:
        page_end = min(end, cursor + timedelta(hours=9999))
        for bar in fetch_hourly(start=cursor, end=page_end):
            if cursor <= bar.open_time < page_end:
                collected[bar.open_time] = bar
        cursor = page_end
    bars = tuple(collected[key] for key in sorted(collected))
    validate_hourly_continuity(bars)
    expected = int((end - start).total_seconds() // 3600)
    if (
        len(bars) != expected
        or bars[0].open_time != start
        or bars[-1].open_time != end - timedelta(hours=1)
    ):
        raise ValueError(f"Bitfinex backfill incomplete: expected={expected} fetched={len(bars)}")
    with HistoricalOHLCVArchive(database) as archive:
        inserted = archive.persist(bars)
        stored = archive.read(
            instrument_id=INSTRUMENT_ID,
            timeframe="1h",
            source_id=SOURCE_ID,
        )
        archive.integrity_check()
    result = {
        "status": "BITFINEX_LONG_HISTORY_INGESTED",
        "source_id": SOURCE_ID,
        "instrument_id": INSTRUMENT_ID,
        "requested_start_utc": start.isoformat(),
        "requested_end_utc": end.isoformat(),
        "fetched_count": len(bars),
        "inserted_count": inserted,
        "stored_count": len(stored),
        "first_open_utc": bars[0].open_time.isoformat(),
        "last_open_utc": bars[-1].open_time.isoformat(),
        "continuity": "PASS",
        "sqlite_integrity": "PASS",
        "canonical_data_sha256": canonical_bar_fingerprint(stored),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True, type=utc_date)
    parser.add_argument("--end", required=True, type=utc_date)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    result = run(
        start=args.start,
        end=args.end,
        database=args.database,
        report_path=args.report,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
