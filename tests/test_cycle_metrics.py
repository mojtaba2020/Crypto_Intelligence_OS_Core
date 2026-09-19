"""Tests for Mojtaba's cycle-research calculations."""

from datetime import UTC, date, datetime
from decimal import Decimal

from crypto_intelligence_os.user_research.cycle_metrics import (
    PRICE_BANDS,
    DailyClose,
    Extremum,
    HalvingEvent,
    extremum_relationships,
    halving_distances,
    price_band_stabilization,
)


def test_peak_trough_ratios_and_day_gaps() -> None:
    extrema = (
        Extremum(
            "trough",
            datetime(2020, 1, 1, tzinfo=UTC),
            Decimal("100"),
            "L1",
        ),
        Extremum(
            "peak",
            datetime(2020, 1, 11, tzinfo=UTC),
            Decimal("400"),
            "H1",
        ),
        Extremum(
            "trough",
            datetime(2020, 1, 21, tzinfo=UTC),
            Decimal("200"),
            "L2",
        ),
        Extremum(
            "peak",
            datetime(2020, 1, 31, tzinfo=UTC),
            Decimal("800"),
            "H2",
        ),
    )

    result = extremum_relationships(extrema)

    trough_to_trough = next(row for row in result if row.relation == "trough_to_trough")
    peak_to_peak = next(row for row in result if row.relation == "peak_to_peak")
    first_rise = next(
        row
        for row in result
        if row.first_label == "L1" and row.second_label == "H1"
    )

    assert trough_to_trough.price_ratio == Decimal("2")
    assert trough_to_trough.days_apart == 20
    assert peak_to_peak.price_ratio == Decimal("2")
    assert peak_to_peak.days_apart == 20
    assert first_rise.price_ratio == Decimal("4")
    assert first_rise.percent_change == Decimal("300")
    assert first_rise.days_apart == 10


def test_halving_distance_is_signed_and_absolute() -> None:
    halving = HalvingEvent(
        datetime(2024, 4, 20, tzinfo=UTC),
        "2024-halving",
    )
    extrema = (
        Extremum(
            "trough",
            datetime(2024, 4, 10, tzinfo=UTC),
            Decimal("50000"),
            "before",
        ),
        Extremum(
            "peak",
            datetime(2024, 5, 20, tzinfo=UTC),
            Decimal("70000"),
            "after",
        ),
    )

    result = halving_distances((halving,), extrema)

    before = next(row for row in result if row.extremum_label == "before")
    after = next(row for row in result if row.extremum_label == "after")
    assert before.signed_days_from_halving == -10
    assert before.absolute_days_from_halving == 10
    assert after.signed_days_from_halving == 30
    assert after.absolute_days_from_halving == 30


def test_requested_logarithmic_price_bands_are_exact() -> None:
    assert tuple((band.lower, band.upper) for band in PRICE_BANDS) == (
        (Decimal("0"), Decimal("10")),
        (Decimal("10"), Decimal("100")),
        (Decimal("100"), Decimal("1000")),
        (Decimal("1000"), Decimal("10000")),
        (Decimal("10000"), Decimal("100000")),
        (Decimal("100000"), Decimal("1000000")),
    )


def test_presence_stabilization_entries_exits_and_boundaries() -> None:
    closes = (
        DailyClose(date(2020, 1, 1), Decimal("9"), "bitstamp"),
        DailyClose(date(2020, 1, 2), Decimal("10"), "bitstamp"),
        DailyClose(date(2020, 1, 3), Decimal("11"), "bitstamp"),
        DailyClose(date(2020, 1, 4), Decimal("99"), "bitstamp"),
        DailyClose(date(2020, 1, 5), Decimal("100"), "bitstamp"),
        DailyClose(date(2020, 1, 6), Decimal("101"), "bitstamp"),
    )

    result = price_band_stabilization(closes, minimum_stable_days=2)

    low = next(row for row in result if row.band_label == "0-10")
    tens = next(row for row in result if row.band_label == "10-100")
    hundreds = next(row for row in result if row.band_label == "100-1000")

    assert low.total_days_present == 1
    assert low.entries == 0
    assert low.exits == 1

    assert tens.total_days_present == 3
    assert tens.episode_count == 1
    assert tens.longest_episode_days == 3
    assert tens.stable_episode_count == 1
    assert tens.stable_days == 3
    assert tens.entries == 1
    assert tens.exits == 1

    assert hundreds.total_days_present == 2
    assert hundreds.entries == 1
    assert hundreds.exits == 0


def test_gap_breaks_stabilization_without_inventing_exit_or_entry() -> None:
    closes = (
        DailyClose(date(2020, 1, 1), Decimal("50"), "bitstamp"),
        DailyClose(date(2020, 1, 2), Decimal("60"), "bitstamp"),
        DailyClose(date(2020, 1, 4), Decimal("70"), "bitstamp"),
        DailyClose(date(2020, 1, 5), Decimal("80"), "bitstamp"),
    )

    result = price_band_stabilization(closes, minimum_stable_days=2)
    tens = next(row for row in result if row.band_label == "10-100")

    assert tens.total_days_present == 4
    assert tens.episode_count == 2
    assert tens.longest_episode_days == 2
    assert tens.stable_episode_count == 2
    assert tens.entries == 0
    assert tens.exits == 0
