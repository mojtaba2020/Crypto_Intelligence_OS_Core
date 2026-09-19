from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from crypto_intelligence_os.market_data import (
    MarketDataSnapshot,
    MarketInstrument,
    MarketType,
    OHLCVBar,
    SnapshotKnowledgeMode,
    Timeframe,
    bars_available_as_of,
    bars_known_by_system_as_of,
)

INSTRUMENT = MarketInstrument(
    instrument_id="market:coinbase:spot:btc-usd",
    venue_id="venue:coinbase",
    base_asset_id="asset:bitcoin",
    quote_asset_id="asset:usd",
    market_type=MarketType.SPOT,
    symbol="BTC/USD",
)


def make_late_ingested_bar() -> OHLCVBar:
    open_time = datetime(2026, 1, 1, tzinfo=UTC)
    close_time = open_time + timedelta(days=1)
    return OHLCVBar(
        instrument_id=INSTRUMENT.instrument_id,
        timeframe=Timeframe.ONE_DAY,
        open_time=open_time,
        close_time=close_time,
        available_at=close_time + timedelta(seconds=1),
        ingested_at=close_time + timedelta(days=30),
        open=Decimal("90000"),
        high=Decimal("92000"),
        low=Decimal("89000"),
        close=Decimal("91000"),
        volume=Decimal("100"),
        source_id="source:coinbase.advanced-trade.public",
    )


def test_system_known_filter_excludes_late_backfill() -> None:
    bar = make_late_ingested_bar()
    cutoff = bar.close_time + timedelta(hours=1)

    assert bars_available_as_of([bar], cutoff) == (bar,)
    assert bars_known_by_system_as_of([bar], cutoff) == ()


def test_snapshot_defaults_to_strict_system_knowledge() -> None:
    bar = make_late_ingested_bar()
    cutoff = bar.close_time + timedelta(hours=1)

    with pytest.raises(ValidationError, match="not yet known"):
        MarketDataSnapshot(
            instrument=INSTRUMENT,
            timeframe=Timeframe.ONE_DAY,
            data_cutoff_time=cutoff,
            bars=(bar,),
        )


def test_reconstructed_market_view_must_be_explicit() -> None:
    bar = make_late_ingested_bar()
    cutoff = bar.close_time + timedelta(hours=1)

    snapshot = MarketDataSnapshot(
        instrument=INSTRUMENT,
        timeframe=Timeframe.ONE_DAY,
        data_cutoff_time=cutoff,
        knowledge_mode=SnapshotKnowledgeMode.RECONSTRUCTED_MARKET_VIEW,
        bars=(bar,),
    )

    assert snapshot.bars == (bar,)
    assert snapshot.knowledge_mode is SnapshotKnowledgeMode.RECONSTRUCTED_MARKET_VIEW
