"""Tests for fail-closed Bitstamp hourly backfill validation."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

import scripts.backfill_bitstamp_hourly as backfill
from crypto_intelligence_os.adapters.market_data.bitstamp import (
    INSTRUMENT_ID,
    SOURCE_ID,
)
from crypto_intelligence_os.adapters.market_data.historical_archive import (
    HistoricalOHLCVArchive,
    canonical_bar_fingerprint,
)
from crypto_intelligence_os.market_data import BarStatus, OHLCVBar, Timeframe


def _bar(open_time: datetime, price: str = "20000") -> OHLCVBar:
    close_time = open_time + timedelta(hours=1)
    value = Decimal(price)
    return OHLCVBar(
        instrument_id=INSTRUMENT_ID,
        timeframe=Timeframe.ONE_HOUR,
        status=BarStatus.FINAL,
        open_time=open_time,
        close_time=close_time,
        available_at=close_time,
        ingested_at=datetime(2026, 9, 27, tzinfo=UTC),
        open=value,
        high=value + Decimal("10"),
        low=value - Decimal("10"),
        close=value,
        volume=Decimal("1"),
        source_id=SOURCE_ID,
    )


def test_backfill_rejects_contiguous_but_incomplete_range(monkeypatch, tmp_path):
    start = datetime(2023, 1, 1, tzinfo=UTC)
    end = start + timedelta(hours=4)
    bars = tuple(_bar(start + timedelta(hours=hour)) for hour in range(3))
    monkeypatch.setattr(backfill, "fetch_hourly_range", lambda **_: bars)

    with pytest.raises(ValueError, match="Bitstamp backfill is incomplete"):
        backfill.run(
            start=start,
            end=end,
            database=tmp_path / "history.sqlite",
            report_path=tmp_path / "report.json",
        )

    assert not (tmp_path / "report.json").exists()


def test_backfill_persists_only_exact_complete_range(monkeypatch, tmp_path):
    start = datetime(2023, 1, 1, tzinfo=UTC)
    end = start + timedelta(hours=4)
    bars = tuple(_bar(start + timedelta(hours=hour)) for hour in range(4))
    monkeypatch.setattr(backfill, "fetch_hourly_range", lambda **_: bars)

    database = tmp_path / "history.sqlite"
    report_path = tmp_path / "report.json"
    report = backfill.run(
        start=start,
        end=end,
        database=database,
        report_path=report_path,
    )

    assert report["expected_count"] == 4
    assert report["fetched_count"] == 4
    assert report["missing_count"] == 0
    assert report["continuity"] == "PASS"
    assert report["sqlite_integrity"] == "PASS"
    assert len(report["canonical_data_sha256"]) == 64
    assert report["first_open_utc"] == start.isoformat()
    assert report["last_open_utc"] == (end - timedelta(hours=1)).isoformat()
    assert report_path.exists()

    with HistoricalOHLCVArchive(database) as archive:
        stored = archive.read(
            instrument_id=INSTRUMENT_ID,
            timeframe="1h",
            source_id=SOURCE_ID,
        )
    assert len(stored) == 4
    assert report["canonical_data_sha256"] == canonical_bar_fingerprint(stored)
