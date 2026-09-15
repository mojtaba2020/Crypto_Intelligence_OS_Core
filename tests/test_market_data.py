from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from crypto_intelligence_os.market_data import (
    BarStatus,
    MarketDataSnapshot,
    MarketInstrument,
    MarketType,
    OHLCVBar,
    Timeframe,
    bars_available_as_of,
)

BTC_USD = MarketInstrument(
    instrument_id="market:example:spot:btc-usd",
    venue_id="venue:example",
    base_asset_id="asset:bitcoin",
    quote_asset_id="asset:usd",
    market_type=MarketType.SPOT,
    symbol="BTC/USD",
)


def make_bar(
    *, day: int, available_delay_minutes: int = 0, status: BarStatus = BarStatus.FINAL
) -> OHLCVBar:
    open_time = datetime(2026, 9, day, tzinfo=UTC)
    close_time = open_time + timedelta(days=1)
    available_at = close_time + timedelta(minutes=available_delay_minutes)
    return OHLCVBar(
        instrument_id=BTC_USD.instrument_id,
        timeframe=Timeframe.ONE_DAY,
        status=status,
        open_time=open_time,
        close_time=close_time,
        available_at=available_at,
        ingested_at=available_at + timedelta(seconds=2),
        open=Decimal("70000"),
        high=Decimal("72000"),
        low=Decimal("69000"),
        close=Decimal("71000"),
        volume=Decimal("1234.50"),
        source_id="source:test:market",
    )


def test_market_identity_distinguishes_base_and_quote_assets() -> None:
    assert BTC_USD.base_asset_id == "asset:bitcoin"
    assert BTC_USD.quote_asset_id == "asset:usd"
    assert BTC_USD.instrument_id.startswith("market:")


def test_market_rejects_same_base_and_quote_asset() -> None:
    with pytest.raises(ValidationError, match="different"):
        MarketInstrument(
            instrument_id="market:example:spot:btc-btc",
            venue_id="venue:example",
            base_asset_id="asset:bitcoin",
            quote_asset_id="asset:bitcoin",
            market_type=MarketType.SPOT,
            symbol="BTC/BTC",
        )


def test_bar_normalizes_aware_timestamps_to_utc() -> None:
    tz = timezone(timedelta(hours=3, minutes=30))
    bar = OHLCVBar(
        instrument_id=BTC_USD.instrument_id,
        timeframe=Timeframe.ONE_HOUR,
        open_time=datetime(2026, 9, 13, 8, 0, tzinfo=tz),
        close_time=datetime(2026, 9, 13, 9, 0, tzinfo=tz),
        available_at=datetime(2026, 9, 13, 9, 0, tzinfo=tz),
        ingested_at=datetime(2026, 9, 13, 9, 0, 2, tzinfo=tz),
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("90"),
        close=Decimal("105"),
        volume=Decimal("10"),
        source_id="source:test:market",
    )
    assert bar.open_time == datetime(2026, 9, 13, 4, 30, tzinfo=UTC)


def test_bar_rejects_impossible_ohlc_values() -> None:
    open_time = datetime(2026, 9, 13, tzinfo=UTC)
    close_time = open_time + timedelta(days=1)
    with pytest.raises(ValidationError, match="high"):
        OHLCVBar(
            instrument_id=BTC_USD.instrument_id,
            timeframe=Timeframe.ONE_DAY,
            open_time=open_time,
            close_time=close_time,
            available_at=close_time,
            ingested_at=close_time,
            open=Decimal("100"),
            high=Decimal("99"),
            low=Decimal("90"),
            close=Decimal("105"),
            volume=Decimal("1"),
            source_id="source:test:market",
        )


def test_final_bar_cannot_exist_before_period_close() -> None:
    open_time = datetime(2026, 9, 13, tzinfo=UTC)
    close_time = open_time + timedelta(days=1)
    with pytest.raises(ValidationError, match="FINAL"):
        OHLCVBar(
            instrument_id=BTC_USD.instrument_id,
            timeframe=Timeframe.ONE_DAY,
            open_time=open_time,
            close_time=close_time,
            available_at=close_time - timedelta(seconds=1),
            ingested_at=close_time,
            open=Decimal("100"),
            high=Decimal("110"),
            low=Decimal("90"),
            close=Decimal("105"),
            volume=Decimal("1"),
            source_id="source:test:market",
        )


def test_point_in_time_filter_excludes_future_bar() -> None:
    first = make_bar(day=10)
    second = make_bar(day=11, available_delay_minutes=15)
    cutoff = second.close_time + timedelta(minutes=5)
    assert bars_available_as_of([second, first], cutoff) == (first,)


def test_snapshot_rejects_future_information() -> None:
    first = make_bar(day=10)
    second = make_bar(day=11, available_delay_minutes=15)
    with pytest.raises(ValidationError, match="unavailable"):
        MarketDataSnapshot(
            instrument=BTC_USD,
            timeframe=Timeframe.ONE_DAY,
            data_cutoff_time=second.close_time + timedelta(minutes=5),
            bars=(first, second),
        )
