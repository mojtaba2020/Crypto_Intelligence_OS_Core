"""Synthetic-only elapsed lead audit tests; no network or market prices."""

from datetime import UTC, datetime

import pytest
from scripts.stage6_hourly_elapsed_lead_audit import audit_elapsed_lead

START = int(datetime(2026, 10, 16, tzinfo=UTC).timestamp())
HOUR = 3600
HORIZONS = (1, 4, 12, 24)


def plan(hours=24):
    return {
        "first_origin_utc": START,
        "stop_origin_exclusive_utc": START + hours * HOUR,
        "horizons_hours": HORIZONS,
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


def test_schedule_overflow_rejected():
    with pytest.raises(ValueError, match="bounded"):
        audit_elapsed_lead(plan(169), [])
