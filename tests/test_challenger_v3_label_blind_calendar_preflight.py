"""Adversarial synthetic-only tests for the 13-horizon label-blind origin gate."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from scripts.challenger_v3_label_blind_calendar_preflight import (
    HORIZONS,
    _advance,
    audit_label_blind_calendar,
)

JAN_1 = int(datetime(2026, 1, 1, tzinfo=UTC).timestamp())
MONDAY = int(datetime(2026, 1, 5, tzinfo=UTC).timestamp())
DEVELOPMENT_END = int(datetime(2027, 1, 1, tzinfo=UTC).timestamp())
RESERVED_START = int(datetime(2028, 1, 1, tzinfo=UTC).timestamp())


def _fixture(horizon: str = "1d", count: int = 3) -> tuple[dict, list[dict]]:
    family, target_bars = HORIZONS[horizon]
    start = MONDAY if family == "weekly" else JAN_1
    plan = {
        "horizon": horizon,
        "first_origin_utc": start,
        "stop_origin_utc": _advance(start, family, count),
        "hypothetical_issue_lag_seconds": 60,
        "review_asof_utc": int(datetime(2026, 12, 30, tzinfo=UTC).timestamp()),
        "approved_dev_end_exclusive_utc": DEVELOPMENT_END,
        "reserved_start_utc": RESERVED_START,
    }
    records = []
    for i in range(count):
        origin = _advance(start, family, i)
        target_end = _advance(origin, family, target_bars)
        records.append(
            {
                "schedule_id": f"origin:{horizon}:{origin}",
                "origin_cutoff_utc": origin,
                "source_first_published_at_utc": origin + 10,
                "source_last_revised_at_utc": origin + 20,
                "source_window_complete": True,
                "source_gap_present": False,
                "target_first_published_at_utc": target_end + 120,
            }
        )
    return plan, records


@pytest.mark.parametrize("horizon", list(HORIZONS))
def test_all_13_requested_horizons_are_provisional_only(horizon: str) -> None:
    plan, records = _fixture(horizon)
    output = audit_label_blind_calendar(plan, records)
    assert output["horizon"] == horizon
    assert output["scheduled_origin_count"] == 3
    assert output["provisionally_eligible_count"] == 3
    assert output["scientific_authorization"] == "NO_RUN"
    assert output["stage7_freeze_authorized"] is False
    assert output["source_provenance_authenticated"] is False
    assert output["independent_effective_n"] == "UNKNOWN"
    assert output["locked_oos_access"] is False


def test_months_follow_calendar_not_fixed_30_day_bars() -> None:
    plan, records = _fixture("3mo")
    actual = audit_label_blind_calendar(plan, records)
    assert datetime.fromtimestamp(actual["origins"][0]["target_end_utc"], tz=UTC) == datetime(
        2026, 4, 1, tzinfo=UTC
    )
    assert datetime.fromtimestamp(actual["origins"][1]["target_end_utc"], tz=UTC) == datetime(
        2026, 5, 1, tzinfo=UTC
    )


def test_missing_scheduled_origin_is_not_replenished() -> None:
    plan, records = _fixture()
    with pytest.raises(ValueError, match="Missing or extra"):
        audit_label_blind_calendar(plan, records[1:])


def test_reordered_or_duplicate_origin_fails_closed() -> None:
    plan, records = _fixture()
    records[1]["origin_cutoff_utc"] = records[0]["origin_cutoff_utc"]
    with pytest.raises(ValueError, match="Unordered"):
        audit_label_blind_calendar(plan, records)


def test_unknown_fields_reject_price_volume_labels_and_predictions() -> None:
    for forbidden in ("close", "volume", "actual_price", "candidate_loss", "future_return"):
        plan, records = _fixture()
        records[1][forbidden] = 42
        with pytest.raises(ValueError, match="non-metadata"):
            audit_label_blind_calendar(plan, records)


def test_unauthenticated_publication_and_revision_timing_blocks_only_affected_slot() -> None:
    plan, records = _fixture()
    records[1]["source_last_revised_at_utc"] = records[1]["origin_cutoff_utc"] + 61
    output = audit_label_blind_calendar(plan, records)
    assert output["scheduled_origin_count"] == 3
    assert output["provisionally_eligible_count"] == 2
    assert output["origins"][1]["reasons"] == ["SOURCE_NOT_KNOWABLE_AT_ISSUE"]


def test_missing_publication_metadata_blocks_without_substituting_bar_close() -> None:
    plan, records = _fixture()
    records[1]["source_first_published_at_utc"] = None
    output = audit_label_blind_calendar(plan, records)
    assert output["origins"][1]["reasons"] == ["SOURCE_PUBLICATION_UNKNOWN"]


def test_immature_target_is_not_counted_as_eligible() -> None:
    plan, records = _fixture()
    records[1]["target_first_published_at_utc"] = None
    output = audit_label_blind_calendar(plan, records)
    assert output["provisionally_eligible_count"] == 2
    assert output["origins"][1]["reasons"] == ["TARGET_NOT_MATURE_AT_REVIEW"]


def test_target_published_before_maturity_is_not_accepted() -> None:
    plan, records = _fixture()
    records[1]["target_first_published_at_utc"] = records[1]["origin_cutoff_utc"]
    output = audit_label_blind_calendar(plan, records)
    assert output["origins"][1]["reasons"] == ["TARGET_PUBLICATION_OUTSIDE_APPROVED_BOUNDARY"]


def test_gap_does_not_reclassify_neighboring_origins() -> None:
    plan, records = _fixture()
    records[1]["source_gap_present"] = True
    output = audit_label_blind_calendar(plan, records)
    assert [r["status"] for r in output["origins"]] == [
        "PROVISIONAL_ELIGIBLE",
        "EXCLUDED",
        "PROVISIONAL_ELIGIBLE",
    ]


def test_target_crossing_approved_boundary_is_excluded_even_if_metadata_says_mature() -> None:
    plan, records = _fixture()
    plan["approved_dev_end_exclusive_utc"] = records[1]["origin_cutoff_utc"] + 86_400
    plan["reserved_start_utc"] = DEVELOPMENT_END
    output = audit_label_blind_calendar(plan, records)
    assert "OUTSIDE_APPROVED_DEVELOPMENT" in output["origins"][1]["reasons"]


def test_late_hypothetical_issuance_cannot_be_called_provisional() -> None:
    plan, records = _fixture("1h")
    plan["hypothetical_issue_lag_seconds"] = 3_600
    output = audit_label_blind_calendar(plan, records)
    assert all("LATE_HYPOTHETICAL_ISSUE" in r["reasons"] for r in output["origins"])


@pytest.mark.parametrize("field", ["source_window_complete", "source_gap_present"])
def test_boolean_fields_must_be_real_booleans(field: str) -> None:
    plan, records = _fixture()
    records[0][field] = 1
    with pytest.raises(ValueError, match="flag"):
        audit_label_blind_calendar(plan, records)


def test_price_like_extra_plan_field_is_rejected() -> None:
    plan, records = _fixture()
    plan["choose_good_origins_by_return"] = True
    with pytest.raises(ValueError, match="closed-schema"):
        audit_label_blind_calendar(plan, records)


def test_unknown_horizon_and_noncanonical_weekly_start_rejected() -> None:
    plan, records = _fixture()
    plan["horizon"] = "1y"
    with pytest.raises(ValueError, match="horizon"):
        audit_label_blind_calendar(plan, records)
    plan, records = _fixture("1w")
    plan["first_origin_utc"] += 86_400
    with pytest.raises(ValueError, match="Noncanonical"):
        audit_label_blind_calendar(plan, records)


def test_overlong_hourly_schedule_rejected_before_audit() -> None:
    plan, _ = _fixture("1h")
    plan["stop_origin_utc"] = plan["first_origin_utc"] + 2_002 * 3_600
    with pytest.raises(ValueError, match="Too many"):
        audit_label_blind_calendar(plan, [])


def test_explicit_schedule_id_uniqueness_prevents_replacement() -> None:
    plan, records = _fixture()
    records[1]["schedule_id"] = records[0]["schedule_id"]
    with pytest.raises(ValueError, match="Schedule ID"):
        audit_label_blind_calendar(plan, records)


@pytest.mark.parametrize(
    "payload",
    [
        "close=123.45;future_return=0.42;model_MAPE=0.01",
        "price:50000",
        "origin:1d:1704067200\\nfuture_price=5",
        "x" * 81,
        "",
    ],
)
def test_schedule_id_is_not_an_unrestricted_label_channel(payload: str) -> None:
    plan, records = _fixture()
    records[1]["schedule_id"] = payload
    with pytest.raises(ValueError, match="Schedule ID"):
        audit_label_blind_calendar(plan, records)


def test_swapping_unique_schedule_ids_changes_identity_and_fails_closed() -> None:
    plan, records = _fixture()
    records[0]["schedule_id"], records[2]["schedule_id"] = (
        records[2]["schedule_id"],
        records[0]["schedule_id"],
    )
    with pytest.raises(ValueError, match="Schedule ID"):
        audit_label_blind_calendar(plan, records)


def test_altering_horizon_to_another_valid_horizon_rejects_old_identity() -> None:
    plan, records = _fixture("1d")
    plan["horizon"] = "2d"
    with pytest.raises(ValueError, match="Schedule ID"):
        audit_label_blind_calendar(plan, records)


def test_non_string_schedule_id_rejected() -> None:
    plan, records = _fixture()
    records[0]["schedule_id"] = 123
    with pytest.raises(ValueError, match="Schedule ID"):
        audit_label_blind_calendar(plan, records)


@pytest.mark.parametrize(
    ("family", "bars"),
    [("hourly", 12), ("daily", 1), ("weekly", 1), ("monthly", 1)],
)
def test_all_bar_arithmetic_rejects_python_datetime_overflow(
    family: str, bars: int
) -> None:
    near_end = int(datetime(9999, 12, 31, 20, tzinfo=UTC).timestamp())
    with pytest.raises(ValueError, match=r"range|calendar"):
        _advance(near_end, family, bars)


def test_hourly_horizon_overflow_rejected_before_provisional_eligibility() -> None:
    first = int(datetime(9999, 12, 31, 20, tzinfo=UTC).timestamp())
    stop = first + 3_600
    end = int(datetime(9999, 12, 31, 23, 59, 59, tzinfo=UTC).timestamp())
    plan = {
        "horizon": "12h",
        "first_origin_utc": first,
        "stop_origin_utc": stop,
        "hypothetical_issue_lag_seconds": 60,
        "review_asof_utc": end,
        "approved_dev_end_exclusive_utc": end,
        "reserved_start_utc": end,
    }
    records = [
        {
            "schedule_id": f"origin:12h:{first}",
            "origin_cutoff_utc": first,
            "source_first_published_at_utc": first,
            "source_last_revised_at_utc": first,
            "source_window_complete": True,
            "source_gap_present": False,
            "target_first_published_at_utc": None,
        }
    ]
    with pytest.raises(ValueError, match="range"):
        audit_label_blind_calendar(plan, records)


@pytest.mark.parametrize(
    "field",
    [
        "review_asof_utc",
        "approved_dev_end_exclusive_utc",
        "reserved_start_utc",
        "stop_origin_utc",
    ],
)
def test_out_of_supported_range_absolute_plan_timestamps_fail(field: str) -> None:
    plan, records = _fixture()
    plan[field] = 10**400
    with pytest.raises(ValueError, match="range"):
        audit_label_blind_calendar(plan, records)


def test_publication_timestamp_beyond_supported_range_rejected() -> None:
    plan, records = _fixture()
    records[0]["source_last_revised_at_utc"] = 10**400
    with pytest.raises(ValueError, match="range"):
        audit_label_blind_calendar(plan, records)


def test_issue_lag_that_overflows_supported_range_rejected() -> None:
    plan, records = _fixture()
    plan["hypothetical_issue_lag_seconds"] = 10**400
    with pytest.raises(ValueError, match="range"):
        audit_label_blind_calendar(plan, records)
