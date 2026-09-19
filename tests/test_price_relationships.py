"""Deterministic historical relationship tests; no exchange calls or fitted forecasts."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from crypto_intelligence_os.market_data.price_relationships import (
    DailyClose,
    historical_price_relationships,
)


BASE = datetime(2026, 1, 1, tzinfo=UTC)


def candle(source: str, day: int, price: int) -> DailyClose:
    return DailyClose(source, BASE + timedelta(days=day), Decimal(price))


def test_ratio_uses_only_completed_nonoverlapping_windows() -> None:
    bars = tuple(candle("bitstamp", i, 100 + 10 * i) for i in range(5))
    result = historical_price_relationships(
        bars, as_of=BASE + timedelta(days=5), horizons=(2,)
    )
    assert len(result) == 1
    assert result[0].observations == 2
    assert result[0].mean_ratio == pytest.approx(((120 / 100) + (140 / 120)) / 2)
    assert result[0].positive_fraction == 1


def test_gap_and_future_bar_not_imputed_or_used() -> None:
    bars = tuple(candle("bitstamp", i, 100 + i) for i in (0, 1, 3, 4, 5, 6))
    result = historical_price_relationships(
        bars, as_of=BASE + timedelta(days=6), horizons=(1,)
    )
    assert len(result) == 1
    assert result[0].observations == 3
    assert result[0].last_day == BASE + timedelta(days=5)


def test_sources_separate_and_invalid_horizons_rejected() -> None:
    bars = tuple(
        candle(source, i, 100 + i)
        for source in ("bitstamp", "bitfinex")
        for i in range(4)
    )
    result = historical_price_relationships(
        bars, as_of=BASE + timedelta(days=4), horizons=(1,)
    )
    assert {row.source for row in result} == {"bitstamp", "bitfinex"}
    with pytest.raises(ValueError, match="Horizons"):
        historical_price_relationships(bars, as_of=BASE, horizons=(0,))
