"""Synthetic-only missing-origin coverage tests."""

from datetime import UTC, datetime

import pytest
from scripts.stage6_hourly_schedule_coverage import (
    audit_github_schedule_arrivals,
    audit_hourly_schedule_coverage,
)

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


def _synthetic_actions_rows() -> list[dict[str, object]]:
    # Synthetic metadata representing the separately observed day-by-day
    # *run-creation counts*. These are NOT actual market forecasts.
    utc_hours = (
        (0, 5, 10, 14, 18, 20, 23),
        (1, 6, 14, 20),
        (0, 5, 11, 16, 20, 23),
        (4, 10, 15, 20, 23),
        (4, 10, 15, 20, 23),
        (4, 9, 14, 19, 22),
        (0, 5, 10, 14, 18, 20, 23),
    )
    rows: list[dict[str, object]] = []
    first = int(datetime(2026, 10, 18, tzinfo=UTC).timestamp())
    for day, hours in enumerate(utc_hours):
        for hour in hours:
            rows.append(
                {
                    "github_run_id": 1000 + len(rows),
                    "created_at_utc": first + day * 24 * HOUR + hour * HOUR + 15 * 60,
                    "workflow_name": "BTC Hourly Prospective Forecasts",
                    "event": "schedule",
                    "conclusion": "success",
                }
            )
    for index in range(15):
        rows.append(
            {
                "github_run_id": 2000 + index,
                "created_at_utc": first + (index % 7) * 24 * HOUR + 2 * HOUR,
                "workflow_name": "Other scheduled workflow",
                "event": "schedule",
                "conclusion": "success",
            }
        )
    return rows


def _week_start_and_stop() -> tuple[int, int]:
    first = int(datetime(2026, 10, 18, tzinfo=UTC).timestamp())
    return first, first + 7 * 24 * HOUR


def test_github_metadata_hourly_vs_four_hour_windows() -> None:
    rows = _synthetic_actions_rows()
    start, stop = _week_start_and_stop()
    result = audit_github_schedule_arrivals(start, stop, rows, api_total_count=len(rows))
    assert result["expected_hourly_trigger_opportunities"] == 168
    assert result["observed_schedule_run_creations"] == 39
    assert result["workflow_creation_count_shortfall_not_slot_attribution"] == 129
    assert result["successful_workflow_conclusions_not_valid_issuances"] == 39
    assert result["four_hour_windows"] == 42
    assert result["four_hour_windows_with_any_run_creation"] == 34
    assert result["four_hour_windows_without_run_creation"] == 8
    assert result["four_hour_windows_with_multiple_run_creations"] == 5
    assert result["other_scheduled_workflow_runs"] == 15
    assert [row["observed_hourly_workflow_runs"] for row in result["by_day"]] == [
        7,
        4,
        6,
        5,
        5,
        5,
        7,
    ]
    assert result["exact_scheduled_slot_assignment_known"] is False
    assert result["independent_publication_time_verified"] is False
    assert result["valid_forecast_count"] == "UNKNOWN"
    assert result["scientific_authorization"] == "NO_RUN"


def test_github_metadata_incomplete_api_page_rejected() -> None:
    rows = _synthetic_actions_rows()
    start, stop = _week_start_and_stop()
    with pytest.raises(ValueError, match="Incomplete"):
        audit_github_schedule_arrivals(start, stop, rows, api_total_count=len(rows) + 1)


def test_github_metadata_duplicate_run_cannot_inflate_coverage() -> None:
    rows = _synthetic_actions_rows()
    start, stop = _week_start_and_stop()
    with pytest.raises(ValueError, match="Duplicate"):
        audit_github_schedule_arrivals(start, stop, [rows[0], rows[0]], api_total_count=2)


def test_github_metadata_no_price_or_future_outcome_fields() -> None:
    rows = _synthetic_actions_rows()
    start, stop = _week_start_and_stop()
    rows[0]["actual_close_usd"] = 999999
    with pytest.raises(ValueError, match="price-blind"):
        audit_github_schedule_arrivals(start, stop, rows, api_total_count=len(rows))


def test_github_metadata_manual_dispatch_not_counted_as_schedule() -> None:
    rows = _synthetic_actions_rows()
    start, stop = _week_start_and_stop()
    rows[0]["event"] = "workflow_dispatch"
    with pytest.raises(ValueError, match="schedule-event"):
        audit_github_schedule_arrivals(start, stop, rows, api_total_count=len(rows))


def test_github_metadata_half_day_or_eight_days_not_allowed() -> None:
    start, stop = _week_start_and_stop()
    with pytest.raises(ValueError, match="whole-day"):
        audit_github_schedule_arrivals(start + 3600, stop, [], api_total_count=0)
    with pytest.raises(ValueError, match="whole-day"):
        audit_github_schedule_arrivals(start, stop + 24 * HOUR, [], api_total_count=0)


def test_github_metadata_created_outside_period_fails_closed() -> None:
    rows = _synthetic_actions_rows()
    start, stop = _week_start_and_stop()
    rows[0]["created_at_utc"] = stop
    with pytest.raises(ValueError, match="out-of-interval"):
        audit_github_schedule_arrivals(start, stop, rows, api_total_count=len(rows))


def test_github_metadata_failed_run_still_counts_creation_not_success() -> None:
    rows = _synthetic_actions_rows()
    start, stop = _week_start_and_stop()
    rows[0]["conclusion"] = "failure"
    result = audit_github_schedule_arrivals(start, stop, rows, api_total_count=len(rows))
    assert result["observed_schedule_run_creations"] == 39
    assert result["successful_workflow_conclusions_not_valid_issuances"] == 38
    assert result["valid_forecast_count"] == "UNKNOWN"
