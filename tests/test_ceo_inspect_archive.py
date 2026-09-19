"""Offline checks for the read-only CEO mission inspection of actual archive records."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from scripts.ceo_inspect_archive import inspect_archive

from crypto_intelligence_os.adapters.market_data import COINBASE_BTC_USD, COINBASE_SOURCE_ID
from crypto_intelligence_os.market_data import BarStatus, OHLCVBar, Timeframe


def create_fixture(tmp_path: Path, *, gap: bool = False) -> tuple[Path, Path]:
    start = datetime(2026, 9, 14, tzinfo=UTC)
    ingested_at = start + timedelta(days=5)
    days = (0, 2) if gap else (0, 1)
    db_path = tmp_path / "btc.sqlite"
    report_path = tmp_path / "report.json"
    with sqlite3.connect(db_path) as db:
        db.execute("CREATE TABLE candles(open_time TEXT PRIMARY KEY, record TEXT NOT NULL)")
        for day in days:
            open_time = start + timedelta(days=day)
            bar = OHLCVBar(
                instrument_id=COINBASE_BTC_USD.instrument_id,
                timeframe=Timeframe.ONE_DAY,
                status=BarStatus.FINAL,
                open_time=open_time,
                close_time=open_time + timedelta(days=1),
                available_at=open_time + timedelta(days=1, seconds=1),
                ingested_at=ingested_at,
                open=Decimal("100"),
                high=Decimal("110"),
                low=Decimal("90"),
                close=Decimal("105"),
                volume=Decimal("3"),
                source_id=COINBASE_SOURCE_ID,
            )
            db.execute(
                "INSERT INTO candles(open_time, record) VALUES (?, ?)",
                (open_time.isoformat(), bar.model_dump_json()),
            )
    report = {
        "status": "COMPLETED",
        "persistence": "PRIVATE_GITHUB_DATA_BRANCH",
        "instrument": COINBASE_BTC_USD.instrument_id,
        "source": COINBASE_SOURCE_ID,
        "archive_total_count": 2,
        "sqlite_sha256": hashlib.sha256(db_path.read_bytes()).hexdigest(),
        "first_archived_bar_utc": start.isoformat(),
        "last_archived_bar_utc": (start + timedelta(days=days[-1])).isoformat(),
        "run_id": "123-1",
        "completed_at_utc": ingested_at.isoformat(),
    }
    report_path.write_text(json.dumps(report))
    return db_path, report_path


def test_ceo_inspector_checks_source_backed_counts_and_provenance(tmp_path: Path) -> None:
    db_path, report_path = create_fixture(tmp_path)
    result = inspect_archive(db_path, report_path)
    assert result["archive_total_count"] == 2
    assert result["last_ingestion_run_id"] == "123-1"
    assert result["sqlite_sha256"] == hashlib.sha256(db_path.read_bytes()).hexdigest()


def test_ceo_inspector_rejects_corrupted_checksum(tmp_path: Path) -> None:
    db_path, report_path = create_fixture(tmp_path)
    report = json.loads(report_path.read_text())
    report["sqlite_sha256"] = "0" * 64
    report_path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="checksum"):
        inspect_archive(db_path, report_path)


def test_ceo_inspector_rejects_missing_day(tmp_path: Path) -> None:
    db_path, report_path = create_fixture(tmp_path, gap=True)
    with pytest.raises(ValueError, match="gap"):
        inspect_archive(db_path, report_path)


def test_ceo_inspector_rejects_fictitious_success(tmp_path: Path) -> None:
    db_path, report_path = create_fixture(tmp_path)
    report = json.loads(report_path.read_text())
    report["status"] = "RUNNING"
    report_path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="Unexpected, failed"):
        inspect_archive(db_path, report_path)
