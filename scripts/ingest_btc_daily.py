#!/usr/bin/env python3
"""Incrementally ingest final BTC/USD daily candles into a private SQLite archive."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts.archive_btc_90d import validate_daily_bars

from crypto_intelligence_os.adapters.market_data import CoinbasePublicCandleSource
from crypto_intelligence_os.adapters.market_data.btc_archive import BTCArchive
from crypto_intelligence_os.market_data import Timeframe

DB_PATH = Path("data/btc_usd_daily.sqlite")
REPORT_PATH = Path("data/btc_ingestion_report.json")


def main() -> int:
    started_at = datetime.now(UTC)
    source = CoinbasePublicCandleSource()
    source_time = source.fetch_server_time()
    end = source_time.replace(hour=0, minute=0, second=0, microsecond=0)
    run_number = os.environ.get("GITHUB_RUN_ID", "").strip()
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1").strip()
    run_id = f"{run_number}-{attempt}" if run_number else started_at.isoformat()
    with BTCArchive(DB_PATH) as store:
        last_open = store.last_open_time()
        # First run: 90 complete days. Later runs: overlap by 2 days to detect revisions.
        start = (
            last_open - timedelta(days=2)
            if last_open is not None
            else end - timedelta(days=90)
        )
        if start >= end:
            raise ValueError("Stored last candle is in the future")
        bars = source.fetch_final_bars(
            timeframe=Timeframe.ONE_DAY, start=start, end=end, as_of=source_time
        )
        validate_daily_bars(bars, start=start, end=end, cutoff=source_time)
        completed_at = max(datetime.now(UTC), *(bar.ingested_at for bar in bars))
        inserted = store.persist(
            bars,
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
            source_time=source_time,
            requested_start=start,
            requested_end=end,
        )
        archived = store.all_bars()
        if not archived:
            raise ValueError("Archive contains no rows")
        validate_daily_bars(
            archived, start=archived[0].open_time, end=end, cutoff=completed_at
        )
        count = store.count()
    checksum = hashlib.sha256(DB_PATH.read_bytes()).hexdigest()
    report: dict[str, str | int] = {
        "run_id": run_id,
        "status": "COMPLETED",
        "worker_type": "DETERMINISTIC_MARKET_DATA_PIPELINE_NOT_AI_AGENT",
        "source": "source:coinbase.advanced-trade.public",
        "instrument": "market:coinbase:spot:btc-usd",
        "start_utc": start.isoformat(),
        "end_exclusive_utc": end.isoformat(),
        "first_archived_bar_utc": archived[0].open_time.isoformat(),
        "last_archived_bar_utc": archived[-1].open_time.isoformat(),
        "source_time_utc": source_time.isoformat(),
        "started_at_utc": started_at.isoformat(),
        "completed_at_utc": completed_at.isoformat(),
        "fetched_count": len(bars),
        "inserted_count": inserted,
        "archive_total_count": count,
        "sqlite_sha256": checksum,
        "persistence": "PRIVATE_GITHUB_DATA_BRANCH",
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        f"ARCHIVE PASS: total={count} new={inserted} fetched={len(bars)} "
        f"through={end.isoformat()} sqlite_sha256={checksum}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
