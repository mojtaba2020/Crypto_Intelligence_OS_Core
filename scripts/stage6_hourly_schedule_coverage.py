"""Offline, price-blind coverage audit of fixed hourly prospective forecast slots.

GitHub run/log timestamps are CLAIMS until matched to provider-hosted records.
No HTTP, file reading, training, scoring, live scheduling or model approval.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

HORIZONS = (1, 4, 12, 24)
PLAN_FIELDS = frozenset({"first_origin_utc", "stop_origin_exclusive_utc", "horizons_hours"})
RECORD_FIELDS = frozenset(
    {
        "github_run_id",
        "origin_hour_utc",
        "horizon_hours",
        "claimed_issued_at_utc",
        "github_log_seen_at_utc",
        "target_close_utc",
    }
)
MAX_HOURS = 168
SECONDS_PER_HOUR = 3_600


def _second(value: object, field: str) -> int:
    if type(value) is not int or not 0 < value < 10**11:
        raise ValueError(f"Invalid positive UTC integer seconds for {field}")
    return value


def audit_hourly_schedule_coverage(
    plan: Mapping[str, object], records: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    """Count every scheduled slot without pretending to authenticate GitHub logs."""
    if not isinstance(plan, Mapping) or set(plan) != PLAN_FIELDS:
        raise ValueError("Exact hourly schedule plan required")
    requested = plan["horizons_hours"]
    if type(requested) is not tuple or requested != HORIZONS:
        raise ValueError("Must audit all four preregistered hourly horizons together")
    start = _second(plan["first_origin_utc"], "schedule start")
    stop = _second(plan["stop_origin_exclusive_utc"], "schedule stop")
    if (
        start % SECONDS_PER_HOUR
        or stop % SECONDS_PER_HOUR
        or stop <= start
        or stop - start > MAX_HOURS * SECONDS_PER_HOUR
    ):
        raise ValueError("Invalid bounded canonical UTC hourly schedule")
    total_hours = (stop - start) // SECONDS_PER_HOUR
    if (
        not isinstance(records, Sequence)
        or isinstance(records, (str, bytes))
        or len(records) > total_hours * len(HORIZONS)
    ):
        raise ValueError("Invalid or oversized metadata sequence")

    by_origin: dict[int, set[int]] = {}
    # A scheduled four-horizon batch is atomic: never stitch together
    # horizons issued by different jobs or at different claimed times.
    origin_batch: dict[int, tuple[int, int]] = {}
    run_origin: dict[int, int] = {}
    seen: set[tuple[int, int]] = set()
    for record in records:
        if not isinstance(record, Mapping) or set(record) != RECORD_FIELDS:
            raise ValueError("Only exact non-outcome forecast metadata allowed")
        run_id = _second(record["github_run_id"], "GitHub run ID")
        origin = _second(record["origin_hour_utc"], "forecast origin")
        horizon = record["horizon_hours"]
        if type(horizon) is not int or horizon not in HORIZONS:
            raise ValueError("Unknown or malformed hourly horizon")
        if not start <= origin < stop or origin % SECONDS_PER_HOUR:
            raise ValueError("Forecast origin outside canonical fixed schedule")
        identity = (origin, horizon)
        if identity in seen:
            raise ValueError("Duplicate forecast at one scheduled origin and horizon")
        seen.add(identity)

        issue = _second(record["claimed_issued_at_utc"], "claimed issuance")
        logged = _second(record["github_log_seen_at_utc"], "GitHub log time")
        target_close = _second(record["target_close_utc"], "target close")
        expected_close = origin + (horizon + 1) * SECONDS_PER_HOUR
        if target_close != expected_close:
            raise ValueError("Forecast target does not match fixed hourly horizon")
        if not origin + SECONDS_PER_HOUR < issue <= logged < target_close:
            raise ValueError("Forecast log not prospectively timed after completed origin")
        batch = origin_batch.setdefault(origin, (run_id, issue))
        if batch != (run_id, issue):
            raise ValueError("One hourly batch must share the same GitHub run and issuance time")
        owner = run_origin.setdefault(run_id, origin)
        if owner != origin:
            raise ValueError("One GitHub run cannot be reused for distinct scheduled origins")
        by_origin.setdefault(origin, set()).add(horizon)

    origin_rows: list[dict[str, object]] = []
    full = partial = missing = 0
    for origin in range(start, stop, SECONDS_PER_HOUR):
        horizons = by_origin.get(origin, set())
        if len(horizons) == len(HORIZONS):
            status = "CLAIMED_COMPLETE_UNVERIFIED"
            full += 1
        elif horizons:
            status = "PARTIAL_HORIZONS_BLOCKED"
            partial += 1
        else:
            status = "NO_LOGGED_FORECAST_BLOCKED"
            missing += 1
        origin_rows.append(
            {
                "origin_hour_utc": origin,
                "status": status,
                "missing_horizons_hours": [h for h in HORIZONS if h not in horizons],
            }
        )
    return {
        "status": "UNVERIFIED_COVERAGE_ONLY" if full == total_hours else "BLOCKED",
        "scheduled_origin_count": total_hours,
        "claimed_complete_origin_count": full,
        "partial_origin_count": partial,
        "missing_origin_count": missing,
        "expected_forecast_count": total_hours * len(HORIZONS),
        "claimed_logged_forecast_count": len(seen),
        "independent_github_log_provenance_verified": False,
        "data_first_publication_authenticated": False,
        "scientific_authorization": "NO_RUN",
        "stage7_freeze_authorized": False,
        "effective_independent_n": "UNKNOWN",
        "origins": origin_rows,
    }


# A separate, price-blind view of GitHub scheduled-run metadata. Workflow-run
# creation is NOT forecast issuance and GitHub's creation time is not a signed
# first-publication timestamp. This helper never recovers missed forecasts.
GITHUB_RUN_FIELDS = frozenset(
    {"github_run_id", "created_at_utc", "workflow_name", "event", "conclusion"}
)
HOURLY_WORKFLOW_NAME = "BTC Hourly Prospective Forecasts"
FOUR_HOURS = 4 * SECONDS_PER_HOUR
SECONDS_PER_DAY = 24 * SECONDS_PER_HOUR


def audit_github_schedule_arrivals(
    start_utc: int,
    stop_utc: int,
    scheduled_runs: Sequence[Mapping[str, object]],
    *,
    api_total_count: int,
) -> dict[str, object]:
    """Bound a COMPLETE API snapshot and count hourly vs 4-hour run arrivals.

    A 4-hour window containing some run is only a *coverage opportunity*.
    It must never be scored as a timely 4-hour forecast publication.
    """
    from datetime import UTC, datetime

    start = _second(start_utc, "first UTC day")
    stop = _second(stop_utc, "exclusive last UTC day")
    if (
        start % SECONDS_PER_DAY
        or stop % SECONDS_PER_DAY
        or stop <= start
        or stop - start > MAX_HOURS * SECONDS_PER_HOUR
    ):
        raise ValueError("Require a bounded whole-day UTC interval")
    if (
        not isinstance(scheduled_runs, Sequence)
        or isinstance(scheduled_runs, (str, bytes))
        or type(api_total_count) is not int
        or api_total_count != len(scheduled_runs)
        or len(scheduled_runs) > 2000
    ):
        raise ValueError("Incomplete, oversized or malformed GitHub API snapshot")

    windows: dict[int, int] = {
        instant: 0 for instant in range(start, stop, FOUR_HOURS)
    }
    by_day: dict[int, dict[str, int | str]] = {
        instant: {
            "utc_date": datetime.fromtimestamp(instant, UTC).date().isoformat(),
            "expected_hourly_runs": 24,
            "observed_hourly_workflow_runs": 0,
            "successful_workflow_conclusions": 0,
        }
        for instant in range(start, stop, SECONDS_PER_DAY)
    }
    seen_ids: set[int] = set()
    total_observed = total_success = 0
    for row in scheduled_runs:
        if not isinstance(row, Mapping) or set(row) != GITHUB_RUN_FIELDS:
            raise ValueError("Exact, price-blind GitHub run metadata required")
        run_id = _second(row["github_run_id"], "GitHub run id")
        created = _second(row["created_at_utc"], "created time")
        if run_id in seen_ids or not start <= created < stop:
            raise ValueError("Duplicate or out-of-interval run")
        seen_ids.add(run_id)
        if row["event"] != "schedule":
            raise ValueError("Only schedule-event API runs are admissible")
        if not isinstance(row["workflow_name"], str) or not row["workflow_name"]:
            raise ValueError("Workflow name must be nonempty text")
        if row["conclusion"] not in {
            "success", "failure", "cancelled", "skipped",
            "timed_out", "neutral", "action_required", None,
        }:
            raise ValueError("Unrecognized workflow-run conclusion")

        if row["workflow_name"] != HOURLY_WORKFLOW_NAME:
            continue
        total_observed += 1
        day = created - (created % SECONDS_PER_DAY)
        window = created - (created % FOUR_HOURS)
        windows[window] += 1
        by_day[day]["observed_hourly_workflow_runs"] += 1
        if row["conclusion"] == "success":
            total_success += 1
            by_day[day]["successful_workflow_conclusions"] += 1

    expected = (stop - start) // SECONDS_PER_HOUR
    nonempty = sum(count > 0 for count in windows.values())
    return {
        "status": "GITHUB_RUN_METADATA_ONLY_NO_FORECAST_ATTESTATION",
        "expected_hourly_trigger_opportunities": expected,
        "observed_schedule_run_creations": total_observed,
        "workflow_creation_count_shortfall_not_slot_attribution": max(
            0, expected - total_observed
        ),
        "successful_workflow_conclusions_not_valid_issuances": total_success,
        "four_hour_windows": len(windows),
        "four_hour_windows_with_any_run_creation": nonempty,
        "four_hour_windows_without_run_creation": len(windows) - nonempty,
        "four_hour_windows_with_multiple_run_creations": sum(
            count > 1 for count in windows.values()
        ),
        "other_scheduled_workflow_runs": len(scheduled_runs) - total_observed,
        "by_day": list(by_day.values()),
        "exact_scheduled_slot_assignment_known": False,
        "independent_publication_time_verified": False,
        "valid_forecast_count": "UNKNOWN",
        "scientific_authorization": "NO_RUN",
    }
