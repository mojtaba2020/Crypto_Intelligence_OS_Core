"""Prevent future-ingested candles from leaking into historical BTC archive replay."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from crypto_intelligence_os.adapters.market_data.btc_archive import BTCArchive
from crypto_intelligence_os.market_data import BarStatus, OHLCVBar, Timeframe


def test_replay_excludes_bars_not_yet_ingested_and_keeps_first_observation(tmp_path: Path) -> None:
    day = datetime(2026, 9, 10, tzinfo=UTC)
    first_ingestion = day + timedelta(days=2)
    late_ingestion = day + timedelta(days=4)

    def bar(open_time: datetime, ingested_at: datetime) -> OHLCVBar:
        return OHLCVBar(
            instrument_id="market:coinbase:spot:btc-usd",
            timeframe=Timeframe.ONE_DAY,
            status=BarStatus.FINAL,
            open_time=open_time,
            close_time=open_time + timedelta(days=1),
            available_at=open_time + timedelta(days=1, seconds=1),
            ingested_at=ingested_at,
            open=Decimal("100"), high=Decimal("110"), low=Decimal("90"),
            close=Decimal("105"), volume=Decimal("2"),
            source_id="source:coinbase.advanced-trade.public",
        )

    with BTCArchive(tmp_path / "btc.sqlite") as archive:
        assert archive.persist(
            (bar(day, first_ingestion), bar(day + timedelta(days=1), late_ingestion)),
            run_id="first", started_at=late_ingestion, completed_at=late_ingestion,
            source_time=late_ingestion, requested_start=day,
            requested_end=day + timedelta(days=2),
        ) == 2
        assert archive.bars_known_as_of(day + timedelta(days=1, hours=12)) == ()
        early = archive.bars_known_as_of(day + timedelta(days=2, hours=1))
        assert len(early) == 1
        assert early[0].open_time == day
        assert early[0].ingested_at == first_ingestion
        assert len(archive.bars_known_as_of(late_ingestion)) == 2
        with pytest.raises(ValueError):
            archive.bars_known_as_of(datetime(2026, 9, 12))
