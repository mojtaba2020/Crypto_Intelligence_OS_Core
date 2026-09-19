"""Exact historical ratio tests across hour, month, leap year and long horizons."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from crypto_intelligence_os.market_data.calendar_price_ratios import (
    PERIODS,
    PricePoint,
    advance_calendar,
    calculate_calendar_ratios,
)


def test_all_requested_periods_are_defined() -> None:
    assert tuple(label for label, _, _ in PERIODS) == (
        "1h", "1d", "1w", "1mo", "3mo", "6mo", "1y", "2y",
        "3y", "4y", "5y", "6y", "7y", "8y",
    )


def test_hourly_ratio_and_future_cutoff_and_source_isolation() -> None:
    start = datetime(2026, 9, 20, tzinfo=UTC)
    points = (
        PricePoint("bitstamp", start, Decimal(100)),
        PricePoint("bitstamp", start + timedelta(hours=1), Decimal(110)),
        PricePoint("bitfinex", start, Decimal(200)),
        PricePoint("bitfinex", start + timedelta(hours=1), Decimal(180)),
    )
    result = calculate_calendar_ratios(
        points, as_of=start + timedelta(hours=1), periods=(("1h", "hour", 1),)
    )
    assert len(result) == 2
    assert result[0].ratio == Decimal("0.9")
    assert result[1].percent_change == Decimal(10)
    assert calculate_calendar_ratios(
        points, as_of=start, periods=(("1h", "hour", 1),)
    ) == ()


def test_missing_exact_endpoint_never_filled() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    points = (
        PricePoint("bitstamp", start, Decimal(100)),
        PricePoint("bitstamp", start + timedelta(days=2), Decimal(120)),
    )
    assert calculate_calendar_ratios(
        points, as_of=start + timedelta(days=2), periods=(("1d", "day", 1),)
    ) == ()


def test_calendar_month_quarter_half_year_and_leap_anniversary() -> None:
    jan = datetime(2024, 1, 1, tzinfo=UTC)
    assert advance_calendar(jan, "month", 1) == datetime(2024, 2, 1, tzinfo=UTC)
    assert advance_calendar(jan, "month", 3) == datetime(2024, 4, 1, tzinfo=UTC)
    assert advance_calendar(jan, "month", 6) == datetime(2024, 7, 1, tzinfo=UTC)
    leap = datetime(2024, 2, 29, tzinfo=UTC)
    assert advance_calendar(leap, "year", 1) == datetime(2025, 2, 28, tzinfo=UTC)
    assert advance_calendar(leap, "year", 8) == datetime(2032, 2, 29, tzinfo=UTC)


def test_year_to_eight_years_and_conflicting_duplicates() -> None:
    start = datetime(2017, 1, 1, tzinfo=UTC)
    points = tuple(
        PricePoint("bitstamp", datetime(year, 1, 1, tzinfo=UTC), Decimal(year))
        for year in range(2017, 2026)
    )
    result = calculate_calendar_ratios(
        points, as_of=datetime(2025, 1, 1, tzinfo=UTC),
        periods=tuple(p for p in PERIODS if p[1] == "year"),
    )
    assert {row.period for row in result} == {f"{n}y" for n in range(1, 9)}
    assert any(row.period == "8y" and row.start == start for row in result)
    with pytest.raises(ValueError, match="Conflicting"):
        calculate_calendar_ratios(
            (points[0], PricePoint("bitstamp", start, Decimal(999))),
            as_of=datetime(2025, 1, 1, tzinfo=UTC),
        )
