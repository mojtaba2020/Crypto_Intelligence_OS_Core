"""Adversarial synthetic-only tests for the 13-horizon label-blind origin gate."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from scripts.challenger_v3_label_blind_calendar_preflight import (
    HORIZONS,
    _advance,
    audit_claimed_asof_input_versions,
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
def test_all_bar_arithmetic_rejects_python_datetime_overflow(family: str, bars: int) -> None:
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


def _asof_fixture() -> tuple[dict, list[dict]]:
    day = 86_400
    origin = JAN_1 + day
    plan = {
        "origin_cutoff_utc": origin,
        "forecast_issued_at_utc": origin + 60,
        "forecast_target_end_utc": origin + day,
    }
    inputs = [
        {
            "kind": "feature_bar",
            "bar_open_utc": origin - day,
            "bar_end_utc": origin,
            "first_observed_at_utc": origin + 5,
            "selected_version_observed_at_utc": origin + 10,
            "selected_version_superseded_at_utc": None,
        },
        {
            "kind": "training_label",
            "bar_open_utc": origin - 2 * day,
            "bar_end_utc": origin - day,
            "first_observed_at_utc": origin - day + 5,
            "selected_version_observed_at_utc": origin - day + 10,
            "selected_version_superseded_at_utc": None,
        },
    ]
    return plan, inputs


def test_asof_both_source_and_label_pretend_ready_only_as_metadata() -> None:
    plan, inputs = _asof_fixture()
    result = audit_claimed_asof_input_versions(plan, inputs)
    assert result["status"] == "UNVERIFIED_ASOF_METADATA_ONLY"
    assert result["blocked_input_count"] == 0
    assert result["scientific_authorization"] == "NO_RUN"
    assert result["stage7_freeze_authorized"] is False
    assert result["real_source_vintages_authenticated"] is False
    assert result["independent_custody_verified"] is False


@pytest.mark.parametrize("kind", ["feature_bar", "training_label"])
def test_asof_late_first_observed_blocks_even_when_bar_closed(kind: str) -> None:
    plan, inputs = _asof_fixture()
    selected = next(record for record in inputs if record["kind"] == kind)
    selected["first_observed_at_utc"] = plan["forecast_issued_at_utc"] + 90
    selected["selected_version_observed_at_utc"] = plan["forecast_issued_at_utc"] + 100
    result = audit_claimed_asof_input_versions(plan, inputs)
    assert result["status"] == "BLOCKED"
    assert "VERSION_NOT_KNOWN_AT_ISSUE" in next(
        item["gaps"] for item in result["inputs"] if item["kind"] == kind
    )


def test_asof_later_revisions_allow_only_preserved_earlier_version() -> None:
    plan, inputs = _asof_fixture()
    future_revision = plan["forecast_issued_at_utc"] + 100
    inputs[0]["selected_version_superseded_at_utc"] = future_revision
    assert audit_claimed_asof_input_versions(plan, inputs)["blocked_input_count"] == 0
    # Retrospectively substituting the corrected version is NOT an as-of view.
    inputs[0]["selected_version_observed_at_utc"] = future_revision
    inputs[0]["selected_version_superseded_at_utc"] = None
    result = audit_claimed_asof_input_versions(plan, inputs)
    assert "VERSION_NOT_KNOWN_AT_ISSUE" in result["inputs"][0]["gaps"]


def test_asof_revision_already_superseded_before_issue_is_blocked() -> None:
    plan, inputs = _asof_fixture()
    inputs[0]["selected_version_superseded_at_utc"] = plan["forecast_issued_at_utc"] - 5
    result = audit_claimed_asof_input_versions(plan, inputs)
    assert result["inputs"][0]["gaps"] == ["SELECTED_VERSION_ALREADY_SUPERSEDED"]


def test_asof_missing_source_or_label_vintage_fails_closed() -> None:
    plan, inputs = _asof_fixture()
    inputs[1]["first_observed_at_utc"] = None
    result = audit_claimed_asof_input_versions(plan, inputs)
    assert result["status"] == "BLOCKED"
    assert result["inputs"][1]["gaps"] == ["SOURCE_OR_LABEL_VINTAGE_UNKNOWN"]


def test_asof_inconsistent_first_insert_after_chosen_version_is_blocked() -> None:
    plan, inputs = _asof_fixture()
    inputs[1]["first_observed_at_utc"] = inputs[1]["selected_version_observed_at_utc"] + 1
    assert (
        "CONTRADICTORY_VINTAGE_CHRONOLOGY"
        in (audit_claimed_asof_input_versions(plan, inputs)["inputs"][1]["gaps"])
    )


def test_asof_duplicate_version_slot_cannot_inflate_input_completeness() -> None:
    plan, inputs = _asof_fixture()
    with pytest.raises(ValueError, match="Duplicate"):
        audit_claimed_asof_input_versions(plan, [*inputs, inputs[0].copy()])


def test_asof_missing_either_source_or_training_label_stays_blocked() -> None:
    plan, inputs = _asof_fixture()
    result = audit_claimed_asof_input_versions(plan, inputs[:1])
    assert result["status"] == "BLOCKED"
    assert result["required_input_kinds_missing"] == ["training_label"]


@pytest.mark.parametrize("payload", [{"close": 50000}, {"next_return": 0.3}])
def test_asof_cannot_smuggle_outcomes_via_metadata(payload: dict) -> None:
    plan, inputs = _asof_fixture()
    inputs[0].update(payload)
    with pytest.raises(ValueError, match="closed-schema"):
        audit_claimed_asof_input_versions(plan, inputs)


def test_asof_cannot_use_target_after_origin_or_issue_before_origin() -> None:
    plan, inputs = _asof_fixture()
    inputs[1]["bar_end_utc"] = plan["origin_cutoff_utc"] + 86_400
    with pytest.raises(ValueError, match="close by"):
        audit_claimed_asof_input_versions(plan, inputs)
    plan, inputs = _asof_fixture()
    plan["forecast_issued_at_utc"] = plan["origin_cutoff_utc"]
    with pytest.raises(ValueError, match="after origin"):
        audit_claimed_asof_input_versions(plan, inputs)


@pytest.mark.parametrize("bad", [None, "a string", [], [{}] * 513])
def test_asof_empty_or_oversized_input_cannot_pass(bad: object) -> None:
    plan, _ = _asof_fixture()
    with pytest.raises(ValueError, match="bounded"):
        audit_claimed_asof_input_versions(plan, bad)


def test_asof_chosen_version_supersession_must_be_after_selected_time() -> None:
    plan, inputs = _asof_fixture()
    inputs[0]["selected_version_superseded_at_utc"] = inputs[0]["selected_version_observed_at_utc"]
    with pytest.raises(ValueError, match="supersession chronology"):
        audit_claimed_asof_input_versions(plan, inputs)


def test_asof_future_clock_or_boolean_timestamp_rejected() -> None:
    plan, inputs = _asof_fixture()
    inputs[0]["first_observed_at_utc"] = True
    with pytest.raises(ValueError, match="UTC integer"):
        audit_claimed_asof_input_versions(plan, inputs)
    plan, inputs = _asof_fixture()
    inputs[1]["selected_version_observed_at_utc"] = 10**400
    with pytest.raises(ValueError, match="range"):
        audit_claimed_asof_input_versions(plan, inputs)


@pytest.mark.parametrize("late_issue_seconds", [0, 1, 86_400])
def test_asof_hindsight_prediction_at_or_after_target_end_fails(
    late_issue_seconds: int,
) -> None:
    plan, inputs = _asof_fixture()
    plan["forecast_issued_at_utc"] = (
        plan["forecast_target_end_utc"] + late_issue_seconds
    )
    with pytest.raises(ValueError, match="before future target end"):
        audit_claimed_asof_input_versions(plan, inputs)


def test_asof_missing_or_backdated_target_end_fails_closed() -> None:
    plan, inputs = _asof_fixture()
    plan.pop("forecast_target_end_utc")
    with pytest.raises(ValueError, match="issuance plan"):
        audit_claimed_asof_input_versions(plan, inputs)
    plan, inputs = _asof_fixture()
    plan["forecast_target_end_utc"] = plan["origin_cutoff_utc"]
    with pytest.raises(ValueError, match="before future target end"):
        audit_claimed_asof_input_versions(plan, inputs)


def test_asof_target_end_is_utc_integer_and_within_calendar() -> None:
    plan, inputs = _asof_fixture()
    plan["forecast_target_end_utc"] = True
    with pytest.raises(ValueError, match="UTC integer"):
        audit_claimed_asof_input_versions(plan, inputs)
    plan, inputs = _asof_fixture()
    plan["forecast_target_end_utc"] = 10**400
    with pytest.raises(ValueError, match="range"):
        audit_claimed_asof_input_versions(plan, inputs)


def test_asof_valid_short_horizon_issuance_remains_unverified() -> None:
    plan, inputs = _asof_fixture()
    plan["forecast_target_end_utc"] = plan["origin_cutoff_utc"] + 3_600
    result = audit_claimed_asof_input_versions(plan, inputs)
    assert result["status"] == "UNVERIFIED_ASOF_METADATA_ONLY"
    assert result["scientific_authorization"] == "NO_RUN"
