"""Offline checks for the 90-day historical archive's completeness gate."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from scripts.archive_btc_90d import validate_daily_bars

from crypto_intelligence_os.adapters.market_data import COINBASE_BTC_USD, COINBASE_SOURCE_ID
from crypto_intelligence_os.market_data import BarStatus, OHLCVBar, Timeframe


def sample_bar(start: datetime, *, ingested_at: datetime) -> OHLCVBar:
    return OHLCVBar(
        instrument_id=COINBASE_BTC_USD.instrument_id,
        timeframe=Timeframe.ONE_DAY,
        status=BarStatus.FINAL,
        open_time=start,
        close_time=start + timedelta(days=1),
        available_at=start + timedelta(days=1, seconds=1),
        ingested_at=ingested_at,
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("90"),
        close=Decimal("105"),
        volume=Decimal("2"),
        source_id=COINBASE_SOURCE_ID,
    )


def test_archive_accepts_two_complete_final_daily_bars() -> None:
    start = datetime(2026, 9, 10, tzinfo=UTC)
    cutoff = start + timedelta(days=3)
    bars = (
        sample_bar(start, ingested_at=cutoff),
        sample_bar(start + timedelta(days=1), ingested_at=cutoff),
    )
    validate_daily_bars(bars, start=start, end=start + timedelta(days=2), cutoff=cutoff)


def test_archive_rejects_missing_daily_bar() -> None:
    start = datetime(2026, 9, 10, tzinfo=UTC)
    cutoff = start + timedelta(days=3)
    with pytest.raises(ValueError, match="Expected 2 daily bars"):
        validate_daily_bars(
            (sample_bar(start, ingested_at=cutoff),),
            start=start,
            end=start + timedelta(days=2),
            cutoff=cutoff,
        )


def test_archive_rejects_unfinished_future_bar() -> None:
    start = datetime(2026, 9, 10, tzinfo=UTC)
    cutoff = start + timedelta(days=1)
    bar = sample_bar(start, ingested_at=cutoff + timedelta(seconds=1))
    with pytest.raises(ValueError, match="Invalid, missing, or future"):
        validate_daily_bars(
            (bar,),
            start=start,
            end=start + timedelta(days=1),
            cutoff=cutoff,
        )
