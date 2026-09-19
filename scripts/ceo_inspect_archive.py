#!/usr/bin/env python3
"""Read-only audit of the actual private BTC/USD archive for the CEO mission console."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import timedelta
from pathlib import Path
from typing import Any

from crypto_intelligence_os.adapters.market_data import COINBASE_BTC_USD, COINBASE_SOURCE_ID
from crypto_intelligence_os.market_data import BarStatus, OHLCVBar, Timeframe

DATA_BRANCH = "data/btc-usd-daily"
DB_PATH = Path("data/btc_usd_daily.sqlite")
REPORT_PATH = Path("data/btc_ingestion_report.json")
REPO = "mojtaba2020/Crypto_Intelligence_OS_Core"


def inspect_archive(db_path: Path, report_path: Path) -> dict[str, str | int]:
    """Return source-backed archive facts; fail instead of displaying misleading data."""
    report: dict[str, Any] = json.loads(report_path.read_text(encoding="utf-8"))
    if (
        report.get("status") != "COMPLETED"
        or report.get("persistence") != "PRIVATE_GITHUB_DATA_BRANCH"
        or report.get("instrument") != COINBASE_BTC_USD.instrument_id
        or report.get("source") != COINBASE_SOURCE_ID
    ):
        raise ValueError("Unexpected, failed or unverified archived mission")
    actual_checksum = hashlib.sha256(db_path.read_bytes()).hexdigest()
    if actual_checksum != report.get("sqlite_sha256"):
        raise ValueError("Archive checksum differs from the recorded ingestion report")

    # Open the database read-only: CEO inspection cannot change the research archive.
    uri = db_path.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        result = conn.execute("PRAGMA integrity_check").fetchone()
        if result is None or result[0] != "ok":
            raise ValueError("SQLite archive failed its integrity check")
        raw_rows = conn.execute("SELECT record FROM candles ORDER BY open_time").fetchall()

    bars = tuple(OHLCVBar.model_validate_json(row[0]) for row in raw_rows)
    count = report.get("archive_total_count")
    if type(count) is not int or not bars or count != len(bars):
        raise ValueError("Archived candle count does not match verified run report")
    for index, bar in enumerate(bars):
        if (
            bar.instrument_id != COINBASE_BTC_USD.instrument_id
            or bar.source_id != COINBASE_SOURCE_ID
            or bar.timeframe is not Timeframe.ONE_DAY
            or bar.status is not BarStatus.FINAL
        ):
            raise ValueError("Archive contains an unexpected instrument, source or candle")
        if index > 0 and bar.open_time != bars[index - 1].open_time + timedelta(days=1):
            raise ValueError("Archived BTC/USD daily timeline contains a gap")
    if bars[0].open_time.isoformat() != report.get("first_archived_bar_utc"):
        raise ValueError("Archived first candle differs from the reported facts")
    if bars[-1].open_time.isoformat() != report.get("last_archived_bar_utc"):
        raise ValueError("Archived last candle differs from the reported facts")

    return {
        "archive_total_count": len(bars),
        "first_archived_bar_utc": bars[0].open_time.isoformat(),
        "last_archived_bar_utc": bars[-1].open_time.isoformat(),
        "last_ingestion_run_id": str(report["run_id"]),
        "last_ingestion_completed_at_utc": str(report["completed_at_utc"]),
        "sqlite_sha256": actual_checksum,
    }


def main() -> int:
    facts = inspect_archive(DB_PATH, REPORT_PATH)
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "")
    if not run_id.isdecimal() or not summary_path:
        raise ValueError("Only a genuine GitHub Actions mission may publish this board")
    source_url = f"https://github.com/{REPO}/tree/{DATA_BRANCH}/data"
    run_url = f"https://github.com/{REPO}/actions/runs/{run_id}"
    report = (
        "## CEO Mission Control — private BTC/USD archive inspection\n\n"
        "**Mission: COMPLETED (real deterministic read-only worker)**\n\n"
        "| Verified archive metric | Actual value |\n|:--|:--|\n"
        f"| Total consecutive daily candles | {facts['archive_total_count']} |\n"
        f"| First completed daily candle | {facts['first_archived_bar_utc']} |\n"
        f"| Last completed daily candle | {facts['last_archived_bar_utc']} |\n"
        f"| Previous successful ingestion | {facts['last_ingestion_completed_at_utc']} |\n"
        f"| Previous ingestion run ID | {facts['last_ingestion_run_id']} |\n\n"
        f"**SQLite checksum (SHA-256):** `{facts['sqlite_sha256']}`\n\n"
        f"[Inspect current mission and live job states]({run_url}) · "
        f"[Browse persisted data in private branch]({source_url})\n\n"
        "**No autonomous AI agents are deployed.** This mission only audits the "
        "existing BTC/USD database; it does not trade or change stored data.\n"
    )
    with Path(summary_path).open("a", encoding="utf-8") as output:
        output.write(report)
    print(
        "CEO ARCHIVE INSPECTION PASS: "
        f"{facts['archive_total_count']} consecutive daily BTC/USD candles; "
        f"last candle {facts['last_archived_bar_utc']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
