"""Tests for the locked preregistered hourly-regime confirmation guards."""

from datetime import UTC, datetime

import pytest

from scripts.confirm_hourly_regime_hypothesis import (
    _assert_exact_primary_period,
    _assert_independent_period,
)


EXPLORATORY = "2024-01-01T00:00:00Z/2024-12-31T23:00:00Z"
PRIMARY = "2023-01-01T00:00:00Z/2023-12-31T23:00:00Z"


def test_independent_period_guard_rejects_exploratory_overlap():
    with pytest.raises(ValueError, match="overlaps the exploratory period"):
        _assert_independent_period(
            datetime(2024, 1, 1, tzinfo=UTC),
            datetime(2024, 12, 31, 23, tzinfo=UTC),
            EXPLORATORY,
        )


def test_independent_period_guard_accepts_locked_primary_year():
    _assert_independent_period(
        datetime(2023, 1, 1, tzinfo=UTC),
        datetime(2023, 12, 31, 23, tzinfo=UTC),
        EXPLORATORY,
    )


def test_exact_primary_period_guard_accepts_full_2023_archive():
    _assert_exact_primary_period(
        datetime(2023, 1, 1, tzinfo=UTC),
        datetime(2023, 12, 31, 23, tzinfo=UTC),
        PRIMARY,
    )


@pytest.mark.parametrize(
    ("first_open", "last_open"),
    [
        (
            datetime(2023, 1, 1, 1, tzinfo=UTC),
            datetime(2023, 12, 31, 23, tzinfo=UTC),
        ),
        (
            datetime(2023, 1, 1, tzinfo=UTC),
            datetime(2023, 12, 31, 22, tzinfo=UTC),
        ),
        (
            datetime(2022, 12, 31, 23, tzinfo=UTC),
            datetime(2023, 12, 31, 23, tzinfo=UTC),
        ),
    ],
)
def test_exact_primary_period_guard_rejects_partial_or_extra_archive(
    first_open, last_open
):
    with pytest.raises(ValueError, match="exactly match"):
        _assert_exact_primary_period(first_open, last_open, PRIMARY)
