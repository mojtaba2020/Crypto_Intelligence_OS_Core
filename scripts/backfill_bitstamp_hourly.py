#!/usr/bin/env python3
"""Backfill validated Bitstamp BTC/USD hourly history into the research archive."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from crypto_intelligence_os.adapters.market_data.bitstamp import (
    INSTRUMENT_ID,
    SOURCE_ID,
    fetch_hourly_range,
)
from crypto_intelligence_os.adapters.market_data.historical_archive import (
    HistoricalOHLCVArchive,
    validate_hourly_continuity,
)


def utc_date(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def run(*, start: datetime, end: datetime, database: Path, report_path: Path) -> dict:
    bars = fetch_hourly_range(start=start, end=end)
    expected_count = int((end - start).total_seconds() // 3600)
    actual_times = {bar.open_time for bar in bars}
    missing_times = []
    cursor = start
    while cursor < end:
        if cursor not in actual_times:
            missing_times.append(cursor.isoformat())
        cursor += timedelta(hours=1)
    validate_hourly_continuity(bars)
    if len(bars) != expected_count or missing_times:
        raise ValueError(
            "Bitstamp backfill is incomplete: "
            f"expected={expected_count} fetched={len(bars)} "
            f"missing={len(missing_times)}"
        )
    if bars[0].open_time != start or bars[-1].open_time != end - timedelta(hours=1):
        raise ValueError(
            "Bitstamp backfill boundaries do not exactly match requested period"
        )

    with HistoricalOHLCVArchive(database) as archive:
        inserted = archive.persist(bars)
        stored = archive.read(
            instrument_id=INSTRUMENT_ID,
            timeframe="1h",
            source_id=SOURCE_ID,
        )
        archive.integrity_check()

    report = {
        "status": "BITSTAMP_LONG_HISTORY_INGESTED",
        "source_id": SOURCE_ID,
        "instrument_id": INSTRUMENT_ID,
        "timeframe": "1h",
        "requested_start_utc": start.isoformat(),
        "requested_end_utc": end.isoformat(),
        "expected_count": expected_count,
        "fetched_count": len(bars),
        "missing_count": len(missing_times),
        "missing_open_times_utc": missing_times[:100],
        "inserted_count": inserted,
        "stored_count": len(stored),
        "first_open_utc": bars[0].open_time.isoformat(),
        "last_open_utc": bars[-1].open_time.isoformat(),
        "continuity": "PASS",
        "sqlite_integrity": "PASS",
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True, type=utc_date)
    parser.add_argument("--end", required=True, type=utc_date)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    if args.start >= args.end:
        raise ValueError("--start must be earlier than --end")
    print(
        json.dumps(
            run(
                start=args.start,
                end=args.end,
                database=args.database,
                report_path=args.report,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
