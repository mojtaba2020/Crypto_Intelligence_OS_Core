"""Synthetic-only missing-origin coverage tests."""

from datetime import UTC, datetime

import pytest
from scripts.stage6_hourly_schedule_coverage import audit_hourly_schedule_coverage

START = int(datetime(2026, 10, 16, tzinfo=UTC).timestamp())
HOUR = 3600


def plan(hours=24):
    return {
        "first_origin_utc": START,
        "stop_origin_exclusive_utc": START + hours * HOUR,
        "horizons_hours": (1, 4, 12, 24),
    }


def four(hour):
    origin = START + hour * HOUR
    return [
        {
            "github_run_id": 100 + hour,
            "origin_hour_utc": origin,
            "horizon_hours": h,
            "claimed_issued_at_utc": origin + HOUR + 60,
            "github_log_seen_at_utc": origin + HOUR + 61,
            "target_close_utc": origin + (h + 1) * HOUR,
        }
        for h in (1, 4, 12, 24)
    ]


def test_six_claimed_slots_leave_eighteen_missing() -> None:
    rows = [item for hour in (0, 6, 11, 16, 20, 22) for item in four(hour)]
    result = audit_hourly_schedule_coverage(plan(), rows)
    assert result["scheduled_origin_count"] == 24
    assert result["claimed_complete_origin_count"] == 6
    assert result["missing_origin_count"] == 18
    assert result["expected_forecast_count"] == 96
    assert result["status"] == "BLOCKED"
    assert result["scientific_authorization"] == "NO_RUN"


def test_complete_synthetic_slots_still_unverified() -> None:
    result = audit_hourly_schedule_coverage(plan(1), four(0))
    assert result["status"] == "UNVERIFIED_COVERAGE_ONLY"
    assert result["independent_github_log_provenance_verified"] is False
    assert result["stage7_freeze_authorized"] is False


def test_late_log_cannot_pass() -> None:
    packet = four(0)[0]
    packet["github_log_seen_at_utc"] = START + 7200
    with pytest.raises(ValueError, match="prospectively"):
        audit_hourly_schedule_coverage(plan(1), [packet])


def test_partial_horizons_not_marked_complete() -> None:
    result = audit_hourly_schedule_coverage(plan(1), four(0)[:2])
    assert result["partial_origin_count"] == 1
    assert result["claimed_complete_origin_count"] == 0
    assert result["origins"][0]["missing_horizons_hours"] == [12, 24]


def test_duplicate_cannot_replenish_missing_hour() -> None:
    row = four(0)[0]
    with pytest.raises(ValueError, match="Duplicate"):
        audit_hourly_schedule_coverage(plan(1), [row, row])


def test_unscheduled_origin_not_rebranded_as_valid() -> None:
    with pytest.raises(ValueError, match="outside"):
        audit_hourly_schedule_coverage(plan(1), four(1))


def test_price_field_forbidden_in_coverage_metadata() -> None:
    row = four(0)[0]
    row["future_close"] = 90_000
    with pytest.raises(ValueError, match="non-outcome"):
        audit_hourly_schedule_coverage(plan(1), [row])


@pytest.mark.parametrize("invalid", [(1,), (4, 1, 12, 24), [1, 4, 12, 24]])
def test_unapproved_horizon_subset_or_order_rejected(invalid) -> None:
    p = plan(1)
    p["horizons_hours"] = invalid
    with pytest.raises(ValueError, match="four"):
        audit_hourly_schedule_coverage(p, [])


def test_oversized_schedule_fails_closed() -> None:
    with pytest.raises(ValueError, match="bounded"):
        audit_hourly_schedule_coverage(plan(169), [])


def test_origin_cannot_be_reassembled_from_two_different_runs() -> None:
    rows = four(0)
    rows[-1]["github_run_id"] = 999
    with pytest.raises(ValueError, match="same GitHub run"):
        audit_hourly_schedule_coverage(plan(1), rows)


def test_one_run_must_use_one_consistent_batch_issuance() -> None:
    rows = four(0)
    rows[-1]["claimed_issued_at_utc"] += 1
    with pytest.raises(ValueError, match="issuance time"):
        audit_hourly_schedule_coverage(plan(1), rows)


def test_same_run_cannot_be_reused_for_distinct_origins() -> None:
    rows = four(0) + four(1)
    for row in rows[4:]:
        row["github_run_id"] = rows[0]["github_run_id"]
    with pytest.raises(ValueError, match="distinct scheduled origins"):
        audit_hourly_schedule_coverage(plan(2), rows)


def test_claimed_issuance_at_source_close_is_too_early() -> None:
    rows = four(0)
    for row in rows:
        row["claimed_issued_at_utc"] = START + HOUR
    with pytest.raises(ValueError, match="prospectively timed"):
        audit_hourly_schedule_coverage(plan(1), rows)


def test_valid_distinct_runs_and_shared_batch_time_remain_unverified() -> None:
    rows = four(0) + four(1)
    result = audit_hourly_schedule_coverage(plan(2), rows)
    assert result["claimed_complete_origin_count"] == 2
    assert result["status"] == "UNVERIFIED_COVERAGE_ONLY"
    assert result["independent_github_log_provenance_verified"] is False
    assert result["scientific_authorization"] == "NO_RUN"
