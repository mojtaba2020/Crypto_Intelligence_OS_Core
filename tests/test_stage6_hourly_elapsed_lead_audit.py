"""Synthetic-only elapsed lead audit tests; no network or market prices."""

from datetime import UTC, datetime

import pytest
from scripts.stage6_hourly_elapsed_lead_audit import audit_elapsed_lead

START = int(datetime(2026, 10, 16, tzinfo=UTC).timestamp())
HOUR = 3600
HORIZONS = (1, 4, 12, 24)


def plan(hours=24, semantics="bar_aligned"):
    return {
        "first_origin_utc": START,
        "stop_origin_exclusive_utc": START + hours * HOUR,
        "horizons_hours": HORIZONS,
        "claim_semantics": semantics,
    }


def record(hour=0, horizon=1, issue_lag=30, publication_lag=30):
    origin = START + hour * HOUR
    return {
        "github_run_id": 123 + hour,
        "origin_hour_utc": origin,
        "horizon_hours": horizon,
        "claimed_issued_at_utc": origin + HOUR + issue_lag,
        "claimed_github_log_seen_at_utc": origin + HOUR + publication_lag,
        "target_close_utc": origin + (horizon + 1) * HOUR,
    }


def test_nominal_hour_can_have_only_30_seconds_of_claimed_lead():
    row = record(issue_lag=3569, publication_lag=3570)
    report = audit_elapsed_lead(plan(1), [row])
    slot = report["slots"][0]
    assert slot["status"] == "CLAIMED_PRE_CLOSE_UNVERIFIED"
    assert slot["claimed_elapsed_lead_seconds"] == 30
    assert report["by_horizon"][0]["min_claimed_elapsed_lead_seconds"] == 30
    assert report["minimum_safe_lead_threshold_approved"] is False
    assert report["scientific_authorization"] == "NO_RUN"
    assert report["stage7_freeze_authorized"] is False


def test_every_absent_hour_and_horizon_in_denominator():
    rows = [record(hour=h, horizon=k) for h in (0, 6, 11, 16, 20, 22) for k in HORIZONS]
    report = audit_elapsed_lead(plan(), rows)
    assert report["expected_origin_horizon_slots"] == 96
    assert report["received_claim_count"] == 24
    assert [r["missing_count"] for r in report["by_horizon"]] == [18] * 4
    assert len(report["slots"]) == 96
    assert report["github_publication_timestamps_independently_verified"] is False


def test_preclosed_horizon_is_not_automatically_complete_hour_lead():
    rows = [record(horizon=h, publication_lag=3570) for h in HORIZONS]
    report = audit_elapsed_lead(plan(1), rows)
    assert [r["claimed_elapsed_lead_seconds"] for r in report["slots"]] == [30, 10830, 39630, 82830]
    assert all(r["status"] == "CLAIMED_PRE_CLOSE_UNVERIFIED" for r in report["slots"])


@pytest.mark.parametrize(
    ("issue_lag", "pub_lag", "status"),
    [
        (-1, 1, "ISSUANCE_CLAIM_BEFORE_ORIGIN_BAR_CLOSED"),
        (3600, 3600, "ISSUANCE_CLAIM_AT_OR_AFTER_MATURITY"),
        (30, 3600, "PUBLICATION_CLAIM_AT_OR_AFTER_MATURITY"),
        (60, 30, "PUBLICATION_CLAIM_BEFORE_ISSUANCE_CLAIM"),
    ],
)
def test_bad_or_late_claims_are_retained_but_blocked(issue_lag, pub_lag, status):
    report = audit_elapsed_lead(plan(1), [record(issue_lag=issue_lag, publication_lag=pub_lag)])
    assert report["slots"][0]["status"] == status
    assert report["slots"][0]["claimed_elapsed_lead_seconds"] is None
    assert report["by_horizon"][0]["blocked_or_unknown_claim_count"] == 1


def test_no_claimed_publication_time_is_unknown_not_valid():
    row = record()
    row["claimed_github_log_seen_at_utc"] = None
    report = audit_elapsed_lead(plan(1), [row])
    assert report["slots"][0]["status"] == "NO_PUBLICATION_WITNESS_CLAIM"
    assert report["by_horizon"][0]["claimed_preclose_count"] == 0


def test_duplicate_origin_horizon_forbidden():
    one = record()
    with pytest.raises(ValueError, match="Duplicate"):
        audit_elapsed_lead(plan(1), [one, one])


def test_different_run_cannot_replenish_missing_horizons_at_one_origin():
    second = record(horizon=4)
    second["github_run_id"] = 124
    with pytest.raises(ValueError, match="replenish"):
        audit_elapsed_lead(plan(1), [record(), second])


def test_run_id_cannot_span_unrelated_origins():
    with pytest.raises(ValueError, match="different origins"):
        audit_elapsed_lead(plan(2), [record(), {**record(hour=1, horizon=4), "github_run_id": 123}])


@pytest.mark.parametrize("bad", [True, "1", 1.5, -1])
def test_invalid_timestamp_type_rejected(bad):
    row = record()
    row["claimed_issued_at_utc"] = bad
    with pytest.raises(ValueError, match="integer UTC"):
        audit_elapsed_lead(plan(1), [row])


def test_extra_outcome_or_price_field_rejected():
    row = record()
    row["future_price"] = 70000
    with pytest.raises(ValueError, match="price-free"):
        audit_elapsed_lead(plan(1), [row])


def test_mismatched_maturity_rejected():
    row = record()
    row["target_close_utc"] += HOUR
    with pytest.raises(ValueError, match="Target close"):
        audit_elapsed_lead(plan(1), [row])


@pytest.mark.parametrize("horizons", [[1, 4, 12, 24], (1, 4), (4, 1, 12, 24)])
def test_noncanonical_horizon_plan_rejected(horizons):
    bad = plan(1)
    bad["horizons_hours"] = horizons
    with pytest.raises(ValueError, match="canonical"):
        audit_elapsed_lead(bad, [])


def test_no_forecast_claims_is_explicitly_blocked():
    report = audit_elapsed_lead(plan(2), [])
    assert report["status"] == "BLOCKED"
    assert report["missing_slot_count"] == 8
    assert report["blocked_or_unknown_claim_count"] == 0
    assert report["received_claim_count"] == 0
    assert report["scientific_authorization"] == "NO_RUN"


def test_partial_claims_cannot_make_packet_appear_unblocked():
    report = audit_elapsed_lead(plan(1), [record()])
    assert report["status"] == "BLOCKED"
    assert report["missing_slot_count"] == 3
    assert report["blocked_or_unknown_claim_count"] == 0


def test_late_claim_blocks_even_when_all_four_horizons_are_present():
    rows = [record(horizon=h) for h in HORIZONS]
    rows[0]["claimed_github_log_seen_at_utc"] = START + 2 * HOUR
    report = audit_elapsed_lead(plan(1), rows)
    assert report["status"] == "BLOCKED"
    assert report["missing_slot_count"] == 0
    assert report["blocked_or_unknown_claim_count"] == 1
    assert report["by_horizon"][0]["claimed_preclose_count"] == 0


def test_complete_synthetic_claims_remain_unverified_and_never_authorize():
    rows = [record(horizon=h) for h in HORIZONS]
    report = audit_elapsed_lead(plan(1), rows)
    assert report["status"] == "UNVERIFIED_ELAPSED_LEAD_METADATA_ONLY"
    assert report["missing_slot_count"] == 0
    assert report["blocked_or_unknown_claim_count"] == 0
    assert report["github_publication_timestamps_independently_verified"] is False
    assert report["scientific_authorization"] == "NO_RUN"
    assert report["stage7_freeze_authorized"] is False


def test_inconsistent_issuance_blocks_whole_batch_and_avoids_leads():
    rows = [record(horizon=h, issue_lag=30, publication_lag=40) for h in HORIZONS]
    rows[2]["claimed_issued_at_utc"] += 2
    # All individual claims are otherwise ordered, pre-close and would pass.
    report = audit_elapsed_lead(plan(1), rows)
    assert report["status"] == "BLOCKED"
    assert report["received_claim_count"] == 4
    assert report["missing_slot_count"] == 0
    assert report["blocked_or_unknown_claim_count"] == 4
    assert len(report["slots"]) == 4
    assert all(
        row["status"] == "INCONSISTENT_BATCH_ISSUANCE_CLAIMS"
        and row["claimed_elapsed_lead_seconds"] is None
        for row in report["slots"]
    )
    assert all(row["claimed_preclose_count"] == 0 for row in report["by_horizon"])
    assert report["scientific_authorization"] == "NO_RUN"
    assert report["stage7_freeze_authorized"] is False


def test_consistent_issuance_may_have_distinct_publication_claims():
    rows = [record(horizon=h, issue_lag=30, publication_lag=30 + i) for i, h in enumerate(HORIZONS)]
    report = audit_elapsed_lead(plan(1), rows)
    assert report["status"] == "UNVERIFIED_ELAPSED_LEAD_METADATA_ONLY"
    assert report["blocked_or_unknown_claim_count"] == 0
    assert report["received_claim_count"] == 4
    assert report["github_publication_timestamps_independently_verified"] is False
    assert report["scientific_authorization"] == "NO_RUN"


def test_different_origins_can_claim_different_issuance_times():
    rows = [
        record(hour=0, horizon=1, issue_lag=30, publication_lag=31),
        record(hour=1, horizon=1, issue_lag=45, publication_lag=46),
    ]
    report = audit_elapsed_lead(plan(2), rows)
    assert report["blocked_or_unknown_claim_count"] == 0
    assert report["missing_slot_count"] == 6
    assert report["status"] == "BLOCKED"
    assert [row["status"] for row in report["slots"] if row["horizon_hours"] == 1] == [
        "CLAIMED_PRE_CLOSE_UNVERIFIED",
        "CLAIMED_PRE_CLOSE_UNVERIFIED",
    ]


def test_schedule_overflow_rejected():
    with pytest.raises(ValueError, match="bounded"):
        audit_elapsed_lead(plan(169), [])


def test_fixed_elapsed_mode_blocks_50_minute_nominal_hour_claim():
    row = record(issue_lag=2, publication_lag=2)
    report = audit_elapsed_lead(plan(1, semantics="fixed_elapsed"), [row])
    assert report["claim_semantics"] == "fixed_elapsed"
    assert report["slots"][0]["status"] == "INSUFFICIENT_CLAIMED_ELAPSED_HORIZON"
    assert report["slots"][0]["claimed_elapsed_lead_seconds"] == 3598
    assert report["by_horizon"][0]["short_elapsed_horizon_count"] == 1
    assert report["by_horizon"][0]["claimed_preclose_count"] == 0
    assert report["blocked_or_unknown_claim_count"] == 1
    assert report["status"] == "BLOCKED"
    assert report["scientific_authorization"] == "NO_RUN"


def test_fixed_elapsed_mode_exact_boundary_and_one_second_short():
    exact = audit_elapsed_lead(
        plan(1, semantics="fixed_elapsed"),
        [record(issue_lag=0, publication_lag=0)],
    )
    assert exact["slots"][0]["status"] == "CLAIMED_PRE_CLOSE_UNVERIFIED"
    assert exact["slots"][0]["claimed_elapsed_lead_seconds"] == 3600
    one_second = audit_elapsed_lead(
        plan(1, semantics="fixed_elapsed"),
        [record(issue_lag=0, publication_lag=1)],
    )
    assert one_second["slots"][0]["status"] == "INSUFFICIENT_CLAIMED_ELAPSED_HORIZON"
    assert one_second["slots"][0]["claimed_elapsed_lead_seconds"] == 3599


def test_fixed_elapsed_mode_blocks_all_four_bar_horizons_after_origin_close():
    rows = [record(horizon=h, issue_lag=20, publication_lag=30) for h in HORIZONS]
    result = audit_elapsed_lead(plan(1, semantics="fixed_elapsed"), rows)
    assert result["received_claim_count"] == 4
    assert result["missing_slot_count"] == 0
    assert result["blocked_or_unknown_claim_count"] == 4
    assert result["status"] == "BLOCKED"
    assert [r["short_elapsed_horizon_count"] for r in result["by_horizon"]] == [1] * 4
    assert all(
        r["status"] == "INSUFFICIENT_CLAIMED_ELAPSED_HORIZON" for r in result["slots"]
    )


def test_bar_aligned_mode_preserves_actual_short_lead_without_claiming_full_hour():
    report = audit_elapsed_lead(plan(1), [record(issue_lag=3569, publication_lag=3570)])
    assert report["claim_semantics"] == "bar_aligned"
    assert report["slots"][0]["claimed_elapsed_lead_seconds"] == 30
    assert report["slots"][0]["status"] == "CLAIMED_PRE_CLOSE_UNVERIFIED"
    assert report["elapsed_horizon_claim_independently_verified"] is False


@pytest.mark.parametrize("bad", [None, "other", 1, True, "FIXED_ELAPSED"])
def test_undefined_horizon_claim_semantics_rejected(bad):
    p = plan(1)
    p["claim_semantics"] = bad
    with pytest.raises(ValueError, match="claim semantics"):
        audit_elapsed_lead(p, [])


def test_unstated_semantics_rejected_instead_of_defaulting():
    p = plan(1)
    del p["claim_semantics"]
    with pytest.raises(ValueError, match="Exact, price-free"):
        audit_elapsed_lead(p, [])


def test_fixed_elapsed_claim_cannot_use_missing_publication_witness():
    row = record(issue_lag=0, publication_lag=0)
    row["claimed_github_log_seen_at_utc"] = None
    result = audit_elapsed_lead(plan(1, semantics="fixed_elapsed"), [row])
    assert result["slots"][0]["status"] == "NO_PUBLICATION_WITNESS_CLAIM"
    assert result["scientific_authorization"] == "NO_RUN"
