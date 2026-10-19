"""Synthetic-only elapsed lead audit tests; no network or market prices."""

import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest
from scripts.stage6_hourly_elapsed_lead_audit import (
    audit_elapsed_lead,
    bind_supplied_git_commit_tree_chain,
    bind_supplied_git_ledger_append,
    reconcile_github_push_bundle,
)

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
        "claimed_publication_upper_bound_utc": origin + HOUR + publication_lag,
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
    row["claimed_publication_upper_bound_utc"] = None
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
    rows[0]["claimed_publication_upper_bound_utc"] = START + 2 * HOUR
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


def test_minimum_elapsed_mode_blocks_50_minute_nominal_hour_claim():
    row = record(issue_lag=2, publication_lag=2)
    report = audit_elapsed_lead(plan(1, semantics="minimum_elapsed"), [row])
    assert report["claim_semantics"] == "minimum_elapsed"
    assert report["slots"][0]["status"] == "INSUFFICIENT_CLAIMED_ELAPSED_HORIZON"
    assert report["slots"][0]["claimed_elapsed_lead_seconds"] == 3598
    assert report["by_horizon"][0]["short_elapsed_horizon_count"] == 1
    assert report["by_horizon"][0]["claimed_preclose_count"] == 0
    assert report["blocked_or_unknown_claim_count"] == 1
    assert report["status"] == "BLOCKED"
    assert report["scientific_authorization"] == "NO_RUN"


def test_minimum_elapsed_mode_exact_boundary_and_one_second_short():
    exact = audit_elapsed_lead(
        plan(1, semantics="minimum_elapsed"),
        [record(issue_lag=0, publication_lag=0)],
    )
    assert exact["slots"][0]["status"] == "CLAIMED_PRE_CLOSE_UNVERIFIED"
    assert exact["slots"][0]["claimed_elapsed_lead_seconds"] == 3600
    one_second = audit_elapsed_lead(
        plan(1, semantics="minimum_elapsed"),
        [record(issue_lag=0, publication_lag=1)],
    )
    assert one_second["slots"][0]["status"] == "INSUFFICIENT_CLAIMED_ELAPSED_HORIZON"
    assert one_second["slots"][0]["claimed_elapsed_lead_seconds"] == 3599


def test_minimum_elapsed_mode_blocks_all_four_bar_horizons_after_origin_close():
    rows = [record(horizon=h, issue_lag=20, publication_lag=30) for h in HORIZONS]
    result = audit_elapsed_lead(plan(1, semantics="minimum_elapsed"), rows)
    assert result["received_claim_count"] == 4
    assert result["missing_slot_count"] == 0
    assert result["blocked_or_unknown_claim_count"] == 4
    assert result["status"] == "BLOCKED"
    assert [r["short_elapsed_horizon_count"] for r in result["by_horizon"]] == [1] * 4
    assert all(r["status"] == "INSUFFICIENT_CLAIMED_ELAPSED_HORIZON" for r in result["slots"])


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


def test_minimum_elapsed_claim_cannot_use_missing_publication_witness():
    row = record(issue_lag=0, publication_lag=0)
    row["claimed_publication_upper_bound_utc"] = None
    result = audit_elapsed_lead(plan(1, semantics="minimum_elapsed"), [row])
    assert result["slots"][0]["status"] == "NO_PUBLICATION_WITNESS_CLAIM"
    assert result["scientific_authorization"] == "NO_RUN"


# These are metadata-only projections of a real GitHub run witnessed on
# 2026-10-18 (run 39136397235). No prices, outcomes, or model weights.
PUSH_SHA = "7a5599d716dd5ce79b0d012885e08ba17c17bcd3"
BASE_SHA = "7570ccfac511145cb9689de5bc57f88597cb5f9e"


def github_bundle():
    run = {
        "id": 39136397235,
        "path": ".github/workflows/btc_hourly_prospective.yml",
        "event": "schedule",
        "status": "completed",
        "conclusion": "success",
        "head_sha": BASE_SHA,
        "created_at": "2026-10-18T14:31:44Z",
        "updated_at": "2026-10-18T14:32:01Z",
    }
    job = {
        "id": 117701666173,
        "run_id": 39136397235,
        "name": "hourly",
        "status": "completed",
        "conclusion": "success",
    }
    commit = {
        "sha": PUSH_SHA,
        "parents": [BASE_SHA],
        "changed_paths": ["research/hourly_forecasts.jsonl", "research/hourly_scores.jsonl"],
    }
    log = [
        "2026-10-18T14:31:58.0993346Z To https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core",
        "2026-10-18T14:31:58.0994084Z    7570ccf..7a5599d  HEAD -> main",
    ]
    origin = datetime(2026, 10, 18, 13, tzinfo=UTC)
    rows = [
        {
            "origin_hour_utc": origin.isoformat(),
            "issued_at_utc": "2026-10-18T14:31:55.995510+00:00",
            "target_close_utc": (origin + timedelta(hours=horizon + 1)).isoformat(),
            "horizon_hours": horizon,
            "version": "hourly-hybrid-ridge-v2",
        }
        for horizon in HORIZONS
    ]
    return run, job, commit, log, rows


def test_actual_hosted_push_bundle_projection_is_consistent_but_unattested():
    bundle = github_bundle()
    res = reconcile_github_push_bundle(*bundle, claim_semantics="bar_aligned")
    assert res["status"] == "GITHUB_RUN_PUSH_PROJECTION_ONLY_UNVERIFIED"
    assert res["run_id_claim"] == 39136397235
    assert res["commit_sha_claim"] == PUSH_SHA
    assert res["github_data_origin_authenticated_by_this_code"] is False
    assert res["projected_forecast_bytes_cryptographically_confirmed"] is False
    assert res["independent_first_publication_attested"] is False
    assert res["scientific_authorization"] == "NO_RUN"
    assert res["observation"]["received_claim_count"] == 4
    assert res["observation"]["missing_slot_count"] == 0
    assert res["observation"]["by_horizon"][0]["claimed_preclose_count"] == 1
    assert res["observation"]["by_horizon"][0]["min_claimed_elapsed_lead_seconds"] == 1679
    assert res["conservative_publication_upper_bound_utc_claim"] == "2026-10-18T14:32:01Z"
    assert res["conservative_publication_upper_bound_ceiled_epoch_second"] == 1792333921
    assert res["publication_bound_source"] == "github_completed_run_updated_at"


def test_actual_hosted_push_timing_blocks_four_minimum_elapsed_claims():
    res = reconcile_github_push_bundle(*github_bundle(), claim_semantics="minimum_elapsed")
    assert res["status"] == "GITHUB_RUN_PUSH_PROJECTION_BLOCKED"
    assert res["observation"]["status"] == "BLOCKED"
    assert res["observation"]["blocked_or_unknown_claim_count"] == 4
    assert all(
        x["status"] == "INSUFFICIENT_CLAIMED_ELAPSED_HORIZON" for x in res["observation"]["slots"]
    )
    assert res["scientific_authorization"] == "NO_RUN"


@pytest.mark.parametrize(
    ("index", "field", "bad", "match"),
    [
        (0, "event", "workflow_dispatch", "scheduled hourly"),
        (0, "conclusion", "failure", "scheduled hourly"),
        (0, "head_sha", "deadbeef", "SHA"),
        (1, "run_id", 39136397234, "belong"),
        (1, "conclusion", "failure", "scheduled hourly"),
        (2, "sha", BASE_SHA, "Push SHA"),
        (2, "parents", [PUSH_SHA], "Push SHA"),
        (2, "changed_paths", ["research/hourly_scores.jsonl"], "ledger commit"),
    ],
)
def test_github_bundle_rejects_mismatched_run_job_commit(index, field, bad, match):
    args = list(github_bundle())
    args[index][field] = bad
    with pytest.raises(ValueError, match=match):
        reconcile_github_push_bundle(*args, claim_semantics="bar_aligned")


def test_github_bundle_rejects_fabricated_late_or_duplicate_push_log():
    run, job, commit, log, rows = github_bundle()
    with pytest.raises(ValueError, match="one GitHub-hosted"):
        reconcile_github_push_bundle(run, job, commit, [*log, log[-1]], rows, "bar_aligned")
    with pytest.raises(ValueError, match="outside"):
        reconcile_github_push_bundle(
            run,
            job,
            commit,
            ["2026-10-18T15:01:00.0000000Z    7570ccf..7a5599d  HEAD -> main"],
            rows,
            "bar_aligned",
        )
    with pytest.raises(ValueError, match="one GitHub-hosted"):
        reconcile_github_push_bundle(
            run, job, commit, ["2026-10-18T14:31:58Z fake push output"], rows, "bar_aligned"
        )


def test_github_bundle_rejects_claim_after_actual_published_push():
    run, job, commit, log, rows = github_bundle()
    rows[0]["issued_at_utc"] = "2026-10-18T14:31:59+00:00"
    with pytest.raises(ValueError, match="Late/or"):
        reconcile_github_push_bundle(run, job, commit, log, rows, "bar_aligned")


def test_github_bundle_rejects_prices_extra_rows_and_horizon_conflicts():
    run, job, commit, log, rows = github_bundle()
    rows[0]["forecast_usd"] = 1
    with pytest.raises(ValueError, match="price-free"):
        reconcile_github_push_bundle(run, job, commit, log, rows, "bar_aligned")
    _, _, _, _, rows = github_bundle()
    rows[0]["target_close_utc"] = "2026-10-18T18:00:00+00:00"
    with pytest.raises(ValueError, match="Target close"):
        reconcile_github_push_bundle(run, job, commit, log, rows, "bar_aligned")
    with pytest.raises(ValueError, match="Four metadata"):
        reconcile_github_push_bundle(run, job, commit, log, rows[:3], "bar_aligned")


def test_github_bundle_late_preclose_witness_is_blocked_at_top_level():
    run, job, commit, log, rows = github_bundle()
    # 13:00 origin, 15:00 first target close; synthetic successful push at 15:01
    # cannot be inside the original completed run, so use an internally consistent
    # later run envelope to test fail-closed maturity accounting.
    run["updated_at"] = "2026-10-18T15:02:00Z"
    log[-1] = "2026-10-18T15:01:00Z    7570ccf..7a5599d  HEAD -> main"
    res = reconcile_github_push_bundle(run, job, commit, log, rows, "bar_aligned")
    assert res["status"] == "GITHUB_RUN_PUSH_PROJECTION_BLOCKED"
    assert res["observation"]["blocked_or_unknown_claim_count"] == 1
    assert res["observation"]["slots"][0]["status"] == "PUBLICATION_CLAIM_AT_OR_AFTER_MATURITY"
    assert res["scientific_authorization"] == "NO_RUN"


def test_early_push_but_late_completed_run_does_not_qualify_the_batch():
    run, job, commit, log, rows = github_bundle()
    # Push was before the 15:00 target, but the completed GitHub run was not.
    run["updated_at"] = "2026-10-18T15:02:00Z"
    result = reconcile_github_push_bundle(run, job, commit, log, rows, "bar_aligned")
    assert result["push_at_utc_claim"] == "2026-10-18T14:31:58.099408+00:00"
    expected_completion = "2026-10-18T15:02:00Z"
    assert result["conservative_publication_upper_bound_utc_claim"] == expected_completion
    assert result["status"] == "GITHUB_RUN_PUSH_PROJECTION_BLOCKED"
    assert result["observation"]["blocked_or_unknown_claim_count"] == 1
    assert result["observation"]["slots"][0]["status"] == "PUBLICATION_CLAIM_AT_OR_AFTER_MATURITY"
    assert result["scientific_authorization"] == "NO_RUN"


def test_missing_or_early_run_completion_metadata_fails_closed():
    run, job, commit, log, rows = github_bundle()
    del run["updated_at"]
    with pytest.raises(ValueError, match="UTC text"):
        reconcile_github_push_bundle(run, job, commit, log, rows, "bar_aligned")
    run, job, commit, log, rows = github_bundle()
    run["updated_at"] = "2026-10-18T14:31:57Z"
    with pytest.raises(ValueError, match="outside"):
        reconcile_github_push_bundle(run, job, commit, log, rows, "bar_aligned")


def test_unbound_projection_never_claims_commit_row_consistency():
    run, job, commit, log, rows = github_bundle()
    # All four rows now claim a different issuance timestamp than the actual
    # GitHub-committed batch. The metadata-only helper cannot detect that;
    # critically, it must NOT claim forecast-content/commit consistency.
    for row in rows:
        row["issued_at_utc"] = "2026-10-18T14:31:55+00:00"
    result = reconcile_github_push_bundle(run, job, commit, log, rows, "bar_aligned")
    assert result["status"] == "GITHUB_RUN_PUSH_PROJECTION_ONLY_UNVERIFIED"
    assert result["projected_forecast_bytes_cryptographically_confirmed"] is False
    assert result["independent_first_publication_attested"] is False
    assert result["scientific_authorization"] == "NO_RUN"


@pytest.mark.parametrize("fraction", [".000001", ".000000001", ".999999999"])
def test_fractional_completion_clock_rounds_forward_and_full_lead_blocks(fraction):
    run, job, commit, log, rows = github_bundle()
    run["created_at"] = "2026-10-18T13:59:59Z"
    run["updated_at"] = f"2026-10-18T14:00:00{fraction}Z"
    log[-1] = "2026-10-18T14:00:00Z    7570ccf..7a5599d  HEAD -> main"
    for row in rows:
        row["issued_at_utc"] = "2026-10-18T14:00:00+00:00"
    result = reconcile_github_push_bundle(run, job, commit, log, rows, "minimum_elapsed")
    assert result["status"] == "GITHUB_RUN_PUSH_PROJECTION_BLOCKED"
    assert result["observation"]["blocked_or_unknown_claim_count"] == 4
    assert result["observation"]["slots"][0]["claimed_elapsed_lead_seconds"] == 3599
    assert result["conservative_publication_upper_bound_ceiled_epoch_second"] == 1792332001


@pytest.mark.parametrize("suffix", ["Z", ".000000000Z"])
def test_exact_whole_second_completion_remains_unverified_not_blocked(suffix):
    run, job, commit, log, rows = github_bundle()
    run["created_at"] = "2026-10-18T13:59:59Z"
    run["updated_at"] = "2026-10-18T14:00:00" + suffix
    log[-1] = "2026-10-18T14:00:00Z    7570ccf..7a5599d  HEAD -> main"
    for row in rows:
        row["issued_at_utc"] = "2026-10-18T14:00:00+00:00"
    result = reconcile_github_push_bundle(run, job, commit, log, rows, "minimum_elapsed")
    assert result["status"] == "GITHUB_RUN_PUSH_PROJECTION_ONLY_UNVERIFIED"
    assert result["observation"]["blocked_or_unknown_claim_count"] == 0
    assert result["observation"]["slots"][0]["claimed_elapsed_lead_seconds"] == 3600
    assert result["independent_first_publication_attested"] is False


@pytest.mark.parametrize("bad", ["2026-10-18T14:00:00.1234567890Z", "2026-10-18T14:00:00+00:00"])
def test_unsupported_github_completion_formats_fail_closed(bad):
    run, job, commit, log, rows = github_bundle()
    run["updated_at"] = bad
    with pytest.raises(ValueError, match="UTC Z timestamp"):
        reconcile_github_push_bundle(run, job, commit, log, rows, "bar_aligned")


def _synthetic_git_append_fixture():
    original = b'{"older_prospective_batch":"opaque"}\n'
    template = {
        "version": "hourly-hybrid-ridge-v2",
        "issued_at_utc": "2026-10-18T14:31:55+00:00",
        "origin_hour_utc": "2026-10-18T13:00:00+00:00",
        "target_hour_utc": "",
        "target_close_utc": "",
        "horizon_hours": 1,
        "origin_close_usd": 10.0,
        "forecast_usd": 11.0,
        "persistence_usd": 10.0,
        "observed_volatility_hourly": 0.1,
        "training_hours": 720,
        "resolved_training_examples": 500,
        "holdout_selected_blend": 0.25,
        "source": "coinbase:exchange:BTC-USD:1h:close",
        "research_only": True,
    }
    origin = datetime(2026, 10, 18, 13, tzinfo=UTC)
    rows = []
    for h in HORIZONS:
        row = {
            **template,
            "horizon_hours": h,
            "target_hour_utc": (origin + timedelta(hours=h)).isoformat(),
            "target_close_utc": (origin + timedelta(hours=h + 1)).isoformat(),
        }
        rows.append(row)
    delta = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows).encode()
    appended = original + delta

    def git_sha(blob):
        return hashlib.sha1(
            b"blob " + str(len(blob)).encode() + b"\0" + blob,
            usedforsecurity=False,
        ).hexdigest()

    projection_keys = (
        "origin_hour_utc",
        "issued_at_utc",
        "target_close_utc",
        "horizon_hours",
        "version",
    )
    projections = [{key: row[key] for key in projection_keys} for row in rows]
    return original, appended, git_sha(original), git_sha(appended), projections


def test_git_blob_byte_append_binding_preserves_exact_metadata_without_price_output():
    args = _synthetic_git_append_fixture()
    result = bind_supplied_git_ledger_append(*args)
    assert result["forecast_rows_bound_to_supplied_git_blob_bytes"] is True
    assert result["appended_forecast_count"] == 4
    assert result["price_or_outcome_values_returned"] is False
    assert result["github_tree_shas_independently_authenticated_by_this_code"] is False
    assert result["independent_first_publication_attested"] is False
    assert result["scientific_authorization"] == "NO_RUN"
    assert all("forecast_usd" not in row for row in result["projected_metadata"])
    assert result["child_blob_sha256"] == hashlib.sha256(args[1]).hexdigest()


def test_git_blob_binding_rejects_a_tampered_projection_even_if_blob_sha_matches():
    old, new, old_sha, new_sha, projection = _synthetic_git_append_fixture()
    projection[0]["issued_at_utc"] = "2026-10-18T14:31:56+00:00"
    with pytest.raises(ValueError, match="differs"):
        bind_supplied_git_ledger_append(old, new, old_sha, new_sha, projection)


def test_git_blob_binding_rejects_changed_forecast_bytes_with_old_sha():
    old, new, old_sha, new_sha, projection = _synthetic_git_append_fixture()
    changed = new.replace(b'"forecast_usd": 11.0', b'"forecast_usd": 12.0')
    with pytest.raises(ValueError, match="Child Git blob SHA"):
        bind_supplied_git_ledger_append(old, changed, old_sha, new_sha, projection)


def test_git_blob_binding_rejects_history_rewrite_even_if_child_rehashed():
    old, new, old_sha, _, projection = _synthetic_git_append_fixture()
    changed = new.replace(b"older_prospective_batch", b"edited_prospective_batch")
    child_sha = hashlib.sha1(
        b"blob " + str(len(changed)).encode() + b"\0" + changed,
        usedforsecurity=False,
    ).hexdigest()
    with pytest.raises(ValueError, match="append-only"):
        bind_supplied_git_ledger_append(old, changed, old_sha, child_sha, projection)


def test_git_blob_binding_rejects_extra_fifth_record_even_if_rehashed():
    old, new, old_sha, _, projection = _synthetic_git_append_fixture()
    changed = new + b'{"extra":"forecast"}\n'
    child_sha = hashlib.sha1(
        b"blob " + str(len(changed)).encode() + b"\0" + changed,
        usedforsecurity=False,
    ).hexdigest()
    with pytest.raises(ValueError, match="Exactly four"):
        bind_supplied_git_ledger_append(old, changed, old_sha, child_sha, projection)


def test_git_blob_binding_rejects_unexpected_future_outcome_field():
    old, new, old_sha, _, projection = _synthetic_git_append_fixture()
    changed = new.replace(
        b'"research_only": true',
        b'"actual_close_usd": 100.0, "research_only": true',
    )
    child_sha = hashlib.sha1(
        b"blob " + str(len(changed)).encode() + b"\0" + changed,
        usedforsecurity=False,
    ).hexdigest()
    with pytest.raises(ValueError, match="schema"):
        bind_supplied_git_ledger_append(old, changed, old_sha, child_sha, projection)


def test_git_blob_binding_rejects_incorrect_parent_sha_and_non_bytes():
    old, new, _, new_sha, projection = _synthetic_git_append_fixture()
    with pytest.raises(ValueError, match="Parent Git blob SHA"):
        bind_supplied_git_ledger_append(old, new, "0" * 40, new_sha, projection)
    with pytest.raises(ValueError, match="exact bytes"):
        bind_supplied_git_ledger_append(old.decode(), new, "0" * 40, new_sha, projection)


def _rewrite_synthetic_appended_row(parent, child, key, value):
    old_rows = [json.loads(line) for line in child[len(parent) :].splitlines()]
    old_rows[0][key] = value
    serialized = "".join(json.dumps(row, sort_keys=True) + "\n" for row in old_rows)
    rewritten = parent + serialized.encode("utf-8")
    child_git_sha = hashlib.sha1(
        b"blob " + str(len(rewritten)).encode() + b"\0" + rewritten,
        usedforsecurity=False,
    ).hexdigest()
    return rewritten, child_git_sha


def test_git_binding_rejects_wrong_target_bar_even_when_projection_unchanged():
    parent, child, parent_sha, _, projection = _synthetic_git_append_fixture()
    changed, child_sha = _rewrite_synthetic_appended_row(
        parent, child, "target_hour_utc", "2026-10-18T20:00:00+00:00"
    )
    with pytest.raises(ValueError, match="Target hour inconsistent"):
        bind_supplied_git_ledger_append(parent, changed, parent_sha, child_sha, projection)


def test_git_binding_rejects_wrong_target_close_even_with_matching_claim():
    parent, child, parent_sha, _, projection = _synthetic_git_append_fixture()
    wrong_close = "2026-10-18T17:00:00+00:00"
    changed, child_sha = _rewrite_synthetic_appended_row(
        parent, child, "target_close_utc", wrong_close
    )
    projection[0]["target_close_utc"] = wrong_close
    with pytest.raises(ValueError, match="Target close inconsistent"):
        bind_supplied_git_ledger_append(parent, changed, parent_sha, child_sha, projection)


@pytest.mark.parametrize("origin", [1792328400, "2026-10-18T13:00:00", "bad timestamp"])
def test_git_binding_rejects_non_utc_or_non_string_origin(origin):
    parent, child, parent_sha, _, projection = _synthetic_git_append_fixture()
    changed, child_sha = _rewrite_synthetic_appended_row(parent, child, "origin_hour_utc", origin)
    projection[0]["origin_hour_utc"] = origin
    with pytest.raises(ValueError, match="Origin"):
        bind_supplied_git_ledger_append(parent, changed, parent_sha, child_sha, projection)


def test_git_binding_rejects_issuance_before_source_candle_close():
    parent, child, parent_sha, _, projection = _synthetic_git_append_fixture()
    early = "2026-10-18T13:30:00+00:00"
    changed, child_sha = _rewrite_synthetic_appended_row(parent, child, "issued_at_utc", early)
    projection[0]["issued_at_utc"] = early
    with pytest.raises(ValueError, match="precedes source candle close"):
        bind_supplied_git_ledger_append(parent, changed, parent_sha, child_sha, projection)


def _git_commit_tree_fixture():
    old, new, old_sha, new_sha, projection = _synthetic_git_append_fixture()
    psha = "a" * 40
    csha = "b" * 40
    ptsha = "c" * 40
    ctsha = "d" * 40
    parent_commit = {"sha": psha, "tree_sha": ptsha}
    child_commit = {
        "sha": csha,
        "tree_sha": ctsha,
        "parents": [psha],
        "changed_paths": [
            "research/hourly_forecasts.jsonl",
            "research/hourly_scores.jsonl",
        ],
    }
    parent_tree = {
        "sha": ptsha,
        "truncated": False,
        "entries": [
            {
                "path": "research/hourly_forecasts.jsonl",
                "mode": "100644",
                "type": "blob",
                "sha": old_sha,
            },
            {
                "path": "research/hourly_scores.jsonl",
                "mode": "100644",
                "type": "blob",
                "sha": "1" * 40,
            },
        ],
    }
    child_tree = {
        "sha": ctsha,
        "truncated": False,
        "entries": [
            {
                "path": "research/hourly_forecasts.jsonl",
                "mode": "100644",
                "type": "blob",
                "sha": new_sha,
            },
            {
                "path": "research/hourly_scores.jsonl",
                "mode": "100644",
                "type": "blob",
                "sha": "2" * 40,
            },
        ],
    }
    return parent_commit, child_commit, parent_tree, child_tree, old, new, projection


def test_supplied_git_commit_tree_chain_binds_to_exact_append_without_go():
    inputs = _git_commit_tree_fixture()
    result = bind_supplied_git_commit_tree_chain(*inputs)
    assert result["forecast_rows_bound_to_supplied_tree_and_blob_metadata"] is True
    assert result["byte_binding"]["appended_forecast_count"] == 4
    assert result["server_first_publication_independently_attested"] is False
    assert result["fetched_git_tree_objects_independently_authenticated_by_this_code"] is False
    assert result["scientific_authorization"] == "NO_RUN"
    assert result["byte_binding"]["price_or_outcome_values_returned"] is False


@pytest.mark.parametrize(
    ("slot", "field", "newvalue", "pattern"),
    [
        (1, "parents", ["f" * 40], "parent SHA"),
        (1, "tree_sha", "e" * 40, "Git tree SHA"),
        (1, "changed_paths", ["research/hourly_scores.jsonl"], "commit paths"),
        (3, "truncated", True, "Complete bounded"),
    ],
)
def test_supplied_git_commit_tree_chain_rejects_mismatched_objects(slot, field, newvalue, pattern):
    values = list(_git_commit_tree_fixture())
    values[slot][field] = newvalue
    with pytest.raises(ValueError, match=pattern):
        bind_supplied_git_commit_tree_chain(*values)


def test_supplied_git_commit_tree_chain_rejects_blob_substitution():
    inputs = list(_git_commit_tree_fixture())
    inputs[3]["entries"][0]["sha"] = "f" * 40
    with pytest.raises(ValueError, match="Child Git blob SHA"):
        bind_supplied_git_commit_tree_chain(*inputs)


def test_supplied_git_commit_tree_chain_rejects_duplicate_paths():
    inputs = list(_git_commit_tree_fixture())
    inputs[3]["entries"].append(dict(inputs[3]["entries"][0]))
    with pytest.raises(ValueError, match="Duplicate or invalid"):
        bind_supplied_git_commit_tree_chain(*inputs)


def test_supplied_git_commit_tree_chain_rejects_non_blob_forecast_path():
    inputs = list(_git_commit_tree_fixture())
    inputs[2]["entries"][0]["type"] = "tree"
    with pytest.raises(ValueError, match="ordinary Git blob"):
        bind_supplied_git_commit_tree_chain(*inputs)


def test_supplied_git_commit_tree_chain_rejects_forged_projection():
    inputs = list(_git_commit_tree_fixture())
    inputs[-1][1]["issued_at_utc"] = "2026-10-18T14:31:56+00:00"
    with pytest.raises(ValueError, match="differs from committed"):
        bind_supplied_git_commit_tree_chain(*inputs)




def test_git_tree_binder_rejects_hidden_unexpected_security_file_change():
    args = list(_git_commit_tree_fixture())
    parent_entry = {
        "path": "src/security.py",
        "mode": "100644",
        "type": "blob",
        "sha": "3" * 40,
    }
    args[2]["entries"].append(parent_entry)
    args[3]["entries"].append({**parent_entry, "sha": "4" * 40})
    with pytest.raises(ValueError, match="changed paths disagree"):
        bind_supplied_git_commit_tree_chain(*args)


def test_git_tree_binder_rejects_unreported_leaf_removal():
    args = list(_git_commit_tree_fixture())
    args[2]["entries"].append(
        {
            "path": "src/security.py",
            "mode": "100644",
            "type": "blob",
            "sha": "3" * 40,
        }
    )
    with pytest.raises(ValueError, match="changed paths disagree"):
        bind_supplied_git_commit_tree_chain(*args)


def test_git_tree_binder_accepts_recursive_directory_tree_sha_changes():
    args = list(_git_commit_tree_fixture())
    args[2]["entries"].append(
        {
            "path": "research",
            "mode": "040000",
            "type": "tree",
            "sha": "5" * 40,
        }
    )
    args[3]["entries"].append(
        {
            "path": "research",
            "mode": "040000",
            "type": "tree",
            "sha": "6" * 40,
        }
    )
    result = bind_supplied_git_commit_tree_chain(*args)
    assert result["scientific_authorization"] == "NO_RUN"
    assert result["forecast_rows_bound_to_supplied_tree_and_blob_metadata"] is True
