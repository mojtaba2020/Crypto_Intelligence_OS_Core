"""Offline, price-blind elapsed-lead audit for BTC hourly forecast claims.

All GitHub run IDs and publication timestamps are caller-supplied assertions,
not authenticated receipts. No network, model fitting, scoring, or promotion.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

HORIZONS = (1, 4, 12, 24)
HOUR = 3_600
MAX_HOURS = 168
PLAN_FIELDS = frozenset({"first_origin_utc", "stop_origin_exclusive_utc", "horizons_hours"})
RECORD_FIELDS = frozenset(
    {
        "github_run_id",
        "origin_hour_utc",
        "horizon_hours",
        "claimed_issued_at_utc",
        "claimed_github_log_seen_at_utc",
        "target_close_utc",
    }
)


def _second(value: object, field: str) -> int:
    if type(value) is not int or not 0 < value < 10**11:
        raise ValueError(f"{field} must be bounded positive integer UTC seconds")
    return value


def audit_elapsed_lead(
    plan: Mapping[str, object], records: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    """Report actual *claimed* elapsed leads and every missing scheduled slot.

    The nominal hourly horizon counts future bars, NOT guaranteed elapsed lead
    from independently published forecast to target maturity. No safety margin
    or 'good lead' decision may be inferred from this metadata-only report.
    """
    if not isinstance(plan, Mapping) or set(plan) != PLAN_FIELDS:
        raise ValueError("Exact, price-free hourly plan required")
    if type(plan["horizons_hours"]) is not tuple or plan["horizons_hours"] != HORIZONS:
        raise ValueError("All four canonical hourly horizons required")
    start = _second(plan["first_origin_utc"], "start")
    stop = _second(plan["stop_origin_exclusive_utc"], "stop")
    if start % HOUR or stop % HOUR or stop <= start or stop - start > MAX_HOURS * HOUR:
        raise ValueError("Invalid bounded hourly plan")
    origin_count = (stop - start) // HOUR
    if (
        not isinstance(records, Sequence)
        or isinstance(records, (bytes, str))
        or len(records) > origin_count * len(HORIZONS)
    ):
        raise ValueError("Invalid or oversized records")

    observed: dict[tuple[int, int], dict[str, object]] = {}
    run_origins: dict[int, int] = {}
    origin_runs: dict[int, int] = {}
    for record in records:
        if not isinstance(record, Mapping) or set(record) != RECORD_FIELDS:
            raise ValueError("Exact price-free forecast metadata required")
        run_id = _second(record["github_run_id"], "github_run_id")
        origin = _second(record["origin_hour_utc"], "origin_hour_utc")
        horizon = record["horizon_hours"]
        if type(horizon) is not int or horizon not in HORIZONS:
            raise ValueError("Unrecognized horizon")
        if not start <= origin < stop or origin % HOUR:
            raise ValueError("Forecast origin outside fixed schedule")
        if (origin, horizon) in observed:
            raise ValueError("Duplicate origin/horizon forecast claim")
        if run_id in run_origins and run_origins[run_id] != origin:
            raise ValueError("Same claimed run ID reused for different origins")
        if origin in origin_runs and origin_runs[origin] != run_id:
            raise ValueError("Different runs cannot silently replenish one origin")
        run_origins[run_id] = origin
        origin_runs[origin] = run_id
        issued = _second(record["claimed_issued_at_utc"], "claimed_issued_at_utc")
        seen_raw = record["claimed_github_log_seen_at_utc"]
        seen = None if seen_raw is None else _second(seen_raw, "claimed_github_log_seen_at_utc")
        close = _second(record["target_close_utc"], "target_close_utc")
        if close != origin + (horizon + 1) * HOUR:
            raise ValueError("Target close conflicts with nominal completed-bar convention")

        if issued < origin + HOUR:
            status = "ISSUANCE_CLAIM_BEFORE_ORIGIN_BAR_CLOSED"
        elif issued >= close:
            status = "ISSUANCE_CLAIM_AT_OR_AFTER_MATURITY"
        elif seen is None:
            status = "NO_PUBLICATION_WITNESS_CLAIM"
        elif seen < issued:
            status = "PUBLICATION_CLAIM_BEFORE_ISSUANCE_CLAIM"
        elif seen >= close:
            status = "PUBLICATION_CLAIM_AT_OR_AFTER_MATURITY"
        else:
            status = "CLAIMED_PRE_CLOSE_UNVERIFIED"

        observed[origin, horizon] = {
            "origin_hour_utc": origin,
            "horizon_hours": horizon,
            "github_run_id_claim": run_id,
            "status": status,
            "claimed_issued_at_utc": issued,
            "claimed_github_log_seen_at_utc": seen,
            "target_close_utc": close,
            "claimed_elapsed_lead_seconds": (
                close - seen if status == "CLAIMED_PRE_CLOSE_UNVERIFIED" else None
            ),
        }

    rows: list[dict[str, object]] = []
    horizon_summaries: list[dict[str, object]] = []
    for origin in range(start, stop, HOUR):
        for horizon in HORIZONS:
            row = observed.get((origin, horizon))
            if row is None:
                row = {
                    "origin_hour_utc": origin,
                    "horizon_hours": horizon,
                    "status": "MISSING_SCHEDULED_FORECAST_CLAIM",
                    "claimed_elapsed_lead_seconds": None,
                }
            rows.append(row)
    for horizon in HORIZONS:
        subset = [r for r in rows if r["horizon_hours"] == horizon]
        leads = [
            r["claimed_elapsed_lead_seconds"]
            for r in subset
            if r["status"] == "CLAIMED_PRE_CLOSE_UNVERIFIED"
        ]
        horizon_summaries.append(
            {
                "horizon_hours": horizon,
                "scheduled_count": origin_count,
                "missing_count": sum(
                    r["status"] == "MISSING_SCHEDULED_FORECAST_CLAIM" for r in subset
                ),
                "claimed_preclose_count": len(leads),
                "blocked_or_unknown_claim_count": sum(
                    r["status"]
                    not in (
                        "MISSING_SCHEDULED_FORECAST_CLAIM",
                        "CLAIMED_PRE_CLOSE_UNVERIFIED",
                    )
                    for r in subset
                ),
                "min_claimed_elapsed_lead_seconds": min(leads) if leads else None,
                "max_claimed_elapsed_lead_seconds": max(leads) if leads else None,
            }
        )
    return {
        "status": "UNVERIFIED_ELAPSED_LEAD_METADATA_ONLY",
        "scheduled_origin_count": origin_count,
        "expected_origin_horizon_slots": origin_count * len(HORIZONS),
        "received_claim_count": len(observed),
        "github_run_identity_independently_verified": False,
        "github_publication_timestamps_independently_verified": False,
        "source_first_available_at_origin_authenticated": False,
        "minimum_safe_lead_threshold_approved": False,
        "independent_effective_n": "UNKNOWN",
        "scientific_authorization": "NO_RUN",
        "stage7_freeze_authorized": False,
        "by_horizon": horizon_summaries,
        "slots": rows,
    }
