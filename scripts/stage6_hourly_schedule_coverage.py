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
    seen: set[tuple[int, int]] = set()
    for record in records:
        if not isinstance(record, Mapping) or set(record) != RECORD_FIELDS:
            raise ValueError("Only exact non-outcome forecast metadata allowed")
        _second(record["github_run_id"], "GitHub run ID")
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
        if not origin + SECONDS_PER_HOUR <= issue <= logged < target_close:
            raise ValueError("Forecast log not prospectively timed after completed origin")
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
