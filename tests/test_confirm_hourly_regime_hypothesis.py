"""Tests for the locked preregistered hourly-regime confirmation guards."""

from datetime import UTC, datetime

import pytest

from scripts.confirm_hourly_regime_hypothesis import _assert_independent_period


EXPLORATORY = "2024-01-01T00:00:00Z/2024-12-31T23:00:00Z"


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
