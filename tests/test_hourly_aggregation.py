"""Offline regression tests for strict hourly-to-multihour aggregation."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from crypto_intelligence_os.market_data.hourly_aggregation import HourCandle, aggregate_fixed_hours


def sample(source: str, hour: int) -> HourCandle:
    return HourCandle(source, datetime(2026, 9, 18, tzinfo=UTC) + timedelta(hours=hour),
                      Decimal(100 + hour), Decimal(110 + hour), Decimal(90 + hour),
                      Decimal(105 + hour), Decimal(2))


def test_complete_two_hour_buckets_and_independent_sources() -> None:
    bars = tuple(sample(source, hour) for source in ("bitstamp", "bitfinex") for hour in range(4))
    result = aggregate_fixed_hours(bars, 2, as_of=datetime(2026, 9, 18, 4, tzinfo=UTC))
    assert len(result) == 4
    assert {x.source for x in result} == {"bitstamp", "bitfinex"}
    assert all(x.volume == Decimal(4) and x.hours == 2 for x in result)
    assert result[0].open == Decimal(100)
    assert result[0].close == Decimal(106)


def test_missing_hour_and_unclosed_bucket_never_pass() -> None:
    bars = (sample("bitstamp", 0), sample("bitstamp", 2), sample("bitstamp", 3))
    assert aggregate_fixed_hours(bars, 2, as_of=datetime(2026, 9, 18, 3, tzinfo=UTC)) == ()
    result = aggregate_fixed_hours(bars, 2, as_of=datetime(2026, 9, 18, 4, tzinfo=UTC))
    assert len(result) == 1
    assert result[0].open_time.hour == 2


def test_conflicting_duplicate_and_naive_cutoff_rejected() -> None:
    candle = sample("bitstamp", 0)
    changed = HourCandle(candle.source, candle.open_time, Decimal(99), candle.high,
                         candle.low, candle.close, candle.volume)
    with pytest.raises(ValueError, match="Conflicting duplicate"):
        aggregate_fixed_hours((candle, changed), 2, as_of=datetime(2026, 9, 18, 2, tzinfo=UTC))
    with pytest.raises(ValueError, match="UTC"):
        aggregate_fixed_hours((candle,), 2, as_of=datetime(2026, 9, 18, 2))
