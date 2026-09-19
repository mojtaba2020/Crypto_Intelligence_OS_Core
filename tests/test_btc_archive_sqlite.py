"""Offline SQLite persistence tests: idempotency, provenance and atomicity."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from crypto_intelligence_os.adapters.market_data import COINBASE_BTC_USD, COINBASE_SOURCE_ID
from crypto_intelligence_os.adapters.market_data.btc_archive import BTCArchive
from crypto_intelligence_os.market_data import BarStatus, OHLCVBar, Timeframe


def make_bar(start: datetime, *, ingested: datetime) -> OHLCVBar:
    return OHLCVBar(
        instrument_id=COINBASE_BTC_USD.instrument_id,
        timeframe=Timeframe.ONE_DAY,
        status=BarStatus.FINAL,
        open_time=start,
        close_time=start + timedelta(days=1),
        available_at=start + timedelta(days=1, seconds=1),
        ingested_at=ingested,
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("90"),
        close=Decimal("105"),
        volume=Decimal("2"),
        source_id=COINBASE_SOURCE_ID,
    )


def record_run(
    store: BTCArchive,
    bars: tuple[OHLCVBar, ...],
    *,
    run_id: str,
    started: datetime,
    completed: datetime,
) -> int:
    return store.persist(
        bars,
        run_id=run_id,
        started_at=started,
        completed_at=completed,
        source_time=started,
        requested_start=bars[0].open_time,
        requested_end=bars[-1].close_time,
    )


def test_archive_persists_and_preserves_first_ingestion(tmp_path: Path) -> None:
    start = datetime(2026, 9, 10, tzinfo=UTC)
    first_seen = start + timedelta(days=3)
    later = first_seen + timedelta(days=1)
    bar = make_bar(start, ingested=first_seen)
    db = tmp_path / "btc.sqlite"
    with BTCArchive(db) as store:
        assert record_run(
            store, (bar,), run_id="one", started=first_seen, completed=first_seen
        ) == 1
        repeated = bar.model_copy(update={"ingested_at": later})
        assert record_run(
            store, (repeated,), run_id="two", started=later, completed=later
        ) == 0
        assert store.count() == 1
        assert store.last_open_time() == start
        assert store.all_bars()[0].ingested_at == first_seen
        store.integrity_check()
    with BTCArchive(db) as reopened:
        assert reopened.count() == 1
        assert reopened.all_bars()[0].ingested_at == first_seen


def test_archive_rejects_conflicting_history_without_partial_commit(tmp_path: Path) -> None:
    start = datetime(2026, 9, 10, tzinfo=UTC)
    seen = start + timedelta(days=3)
    bar = make_bar(start, ingested=seen)
    with BTCArchive(tmp_path / "btc.sqlite") as store:
        assert record_run(
            store, (bar,), run_id="one", started=seen, completed=seen
        ) == 1
        conflicting = bar.model_copy(update={"close": Decimal("106")})
        with pytest.raises(ValueError, match="Historical candle revision"):
            record_run(
                store,
                (make_bar(start - timedelta(days=1), ingested=seen), conflicting),
                run_id="two",
                started=seen,
                completed=seen,
            )
        assert store.count() == 1
        assert store.all_bars()[0].close == Decimal("105")


def test_archive_rejects_future_candle(tmp_path: Path) -> None:
    start = datetime(2026, 9, 10, tzinfo=UTC)
    ingested = start + timedelta(days=2)
    bar = make_bar(start, ingested=ingested)
    with BTCArchive(tmp_path / "btc.sqlite") as store:
        with pytest.raises(ValueError, match="Invalid candle"):
            record_run(
                store, (bar,), run_id="one", started=start, completed=ingested
            )
        assert store.count() == 0
