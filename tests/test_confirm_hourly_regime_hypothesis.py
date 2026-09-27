"""Tests for the locked preregistered hourly-regime confirmation guards."""

import copy
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.confirm_hourly_regime_hypothesis import (
    _assert_exact_primary_period,
    _assert_independent_period,
    _validate_locked_preregistration,
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


def _locked_preregistration():
    path = Path("research/prereg_range_mean_6h_down_low_vol_12h_v1.json")
    return json.loads(path.read_text(encoding="utf-8"))


def test_locked_preregistration_is_accepted_unchanged():
    _validate_locked_preregistration(_locked_preregistration())


@pytest.mark.parametrize(
    ("section", "key", "bad_value"),
    [
        ("hypothesis", "feature", "other_feature"),
        ("hypothesis", "horizon_hours", 24),
        ("hypothesis", "regime", "up__low_vol"),
        ("hypothesis", "model", "ridge_alpha_2"),
        ("hypothesis", "scaling", "global_zscore"),
        ("hypothesis", "benchmark", "zero_return"),
        ("hypothesis", "loss", "squared_error"),
        ("acceptance_rule", "minimum_regime_samples", 39),
        ("acceptance_rule", "bootstrap_method", "iid"),
        ("acceptance_rule", "calendar_block_length_days", 3),
        ("acceptance_rule", "bootstrap_repetitions", 9999),
        ("acceptance_rule", "must_beat_persistence", False),
        ("acceptance_rule", "independent_period_required", False),
        ("acceptance_rule", "promotion_after_single_pass", True),
        ("acceptance_rule", "promotion_requires_replication", False),
        (
            "acceptance_rule",
            "primary_requirement",
            "point estimate improvement > 0",
        ),
        (
            "created_from_exploratory_dataset",
            "period",
            "2022-01-01T00:00:00Z/2022-12-31T23:00:00Z",
        ),
        (
            "confirmatory_data",
            "primary_period",
            "2022-01-01T00:00:00Z/2022-12-31T23:00:00Z",
        ),
        ("confirmatory_data", "primary_source", "OtherExchange"),
        (
            "confirmatory_data",
            "no_threshold_tuning_on_confirmatory_data",
            False,
        ),
    ],
)
def test_locked_preregistration_rejects_parameter_drift(
    section, key, bad_value
):
    prereg = copy.deepcopy(_locked_preregistration())
    prereg[section][key] = bad_value
    with pytest.raises(ValueError):
        _validate_locked_preregistration(prereg)


def test_locked_preregistration_rejects_unlocked_status():
    prereg = copy.deepcopy(_locked_preregistration())
    prereg["status"] = "EXPLORATORY"
    with pytest.raises(ValueError, match="not in locked preregistered status"):
        _validate_locked_preregistration(prereg)


def test_locked_preregistration_rejects_post_access_method_change():
    prereg = copy.deepcopy(_locked_preregistration())
    prereg["methodology_amendment_before_confirmatory_data_access"][
        "status"
    ] = "CHANGED_AFTER_DATA_ACCESS"
    with pytest.raises(ValueError, match="not locked before confirmation"):
        _validate_locked_preregistration(prereg)
