#!/usr/bin/env python3
"""Synthetic-only, label-blind Stage-6 calendar feasibility preflight.

NO provider/filesystem access, model fits, price data or permission to use locked OOS.
Caller-supplied publication metadata is not independently authenticated here.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

HORIZONS: dict[str, tuple[str, int]] = {
    "1h": ("hourly", 1),
    "2h": ("hourly", 2),
    "3h": ("hourly", 3),
    "4h": ("hourly", 4),
    "12h": ("hourly", 12),
    "1d": ("daily", 1),
    "2d": ("daily", 2),
    "3d": ("daily", 3),
    "1w": ("weekly", 1),
    "2w": ("weekly", 2),
    "3w": ("weekly", 3),
    "1mo": ("monthly", 1),
    "3mo": ("monthly", 3),
}
PLAN_KEYS = frozenset(
    {
        "horizon",
        "first_origin_utc",
        "stop_origin_utc",
        "hypothetical_issue_lag_seconds",
        "review_asof_utc",
        "approved_dev_end_exclusive_utc",
        "reserved_start_utc",
    }
)
RECORD_KEYS = frozenset(
    {
        "schedule_id",
        "origin_cutoff_utc",
        "source_first_published_at_utc",
        "source_last_revised_at_utc",
        "source_window_complete",
        "source_gap_present",
        "target_first_published_at_utc",
    }
)
MAX_ORIGINS = 2_000


def _strict_int(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"Invalid nonnegative UTC integer: {label}")
    return value


def _utc(timestamp: int) -> datetime:
    try:
        return datetime.fromtimestamp(timestamp, tz=UTC)
    except (OverflowError, OSError, ValueError) as exc:
        raise ValueError("Timestamp outside supported datetime range") from exc


def _canonical(timestamp: int, family: str) -> bool:
    date = _utc(timestamp)
    if date.minute or date.second or date.microsecond:
        return False
    if family == "hourly":
        return True
    if date.hour:
        return False
    if family == "daily":
        return True
    if family == "weekly":
        return date.weekday() == 0
    return date.day == 1


def _advance(timestamp: int, family: str, bars: int) -> int:
    if family == "monthly":
        date = _utc(timestamp)
        absolute_month = date.year * 12 + date.month - 1 + bars
        year, month_zero = divmod(absolute_month, 12)
        try:
            return int(datetime(year, month_zero + 1, 1, tzinfo=UTC).timestamp())
        except ValueError as exc:
            raise ValueError("Monthly horizon exceeds supported calendar") from exc
    seconds = {"hourly": 3_600, "daily": 86_400, "weekly": 604_800}[family]
    return timestamp + bars * seconds


def audit_label_blind_calendar(
    plan: Mapping[str, object],
    records: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Audit a *fixed* complete schedule; preserve rejected origin slots.

    Output says PROVISIONAL only: supplied timestamps are assertions, not
    trusted provider revision history, isolation approval, labels or power.
    """
    if not isinstance(plan, Mapping) or set(plan) != PLAN_KEYS:
        raise ValueError("Unrecognized or incomplete closed-schema calendar plan")
    horizon = plan["horizon"]
    if not isinstance(horizon, str) or horizon not in HORIZONS:
        raise ValueError("Unknown forecast horizon")
    family, bars = HORIZONS[horizon]
    first = _strict_int(plan["first_origin_utc"], "first_origin_utc")
    stop = _strict_int(plan["stop_origin_utc"], "stop_origin_utc")
    lag = _strict_int(plan["hypothetical_issue_lag_seconds"], "issue lag")
    asof = _strict_int(plan["review_asof_utc"], "review as-of")
    dev_end = _strict_int(plan["approved_dev_end_exclusive_utc"], "dev end")
    reserved = _strict_int(plan["reserved_start_utc"], "reserved start")
    if not 0 < first < stop or not first < asof or not 0 < dev_end <= reserved:
        raise ValueError("Invalid calendar or reserved-boundary order")
    if not _canonical(first, family) or not _canonical(stop, family):
        raise ValueError("Noncanonical UTC origin boundary")

    origins = []
    cursor = first
    while cursor < stop:
        origins.append(cursor)
        if len(origins) > MAX_ORIGINS:
            raise ValueError("Too many proposed origins in one preflight")
        cursor = _advance(cursor, family, 1)
    if cursor != stop:
        raise ValueError("Stop must align with the next canonical origin boundary")
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
        raise ValueError("Calendar records must be a sequence of metadata mappings")
    if len(records) != len(origins):
        raise ValueError("Missing or extra scheduled origin: do not replenish gaps")

    results: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for expected, record in zip(origins, records, strict=True):
        if not isinstance(record, Mapping) or set(record) != RECORD_KEYS:
            raise ValueError("Rejected non-metadata, price, outcome or unknown fields")
        record_id = record["schedule_id"]
        if (
            not isinstance(record_id, str)
            or not record_id.strip()
            or len(record_id) > 80
            or record_id in seen_ids
        ):
            raise ValueError("Invalid or duplicate immutable schedule ID")
        seen_ids.add(record_id)
        origin = _strict_int(record["origin_cutoff_utc"], "origin cutoff")
        if origin != expected:
            raise ValueError("Unordered, substituted or missing scheduled origin")
        if type(record["source_window_complete"]) is not bool:
            raise ValueError("Invalid source completeness flag")
        if type(record["source_gap_present"]) is not bool:
            raise ValueError("Invalid source gap flag")
        timestamps: dict[str, int | None] = {}
        for field in (
            "source_first_published_at_utc",
            "source_last_revised_at_utc",
            "target_first_published_at_utc",
        ):
            value = record[field]
            timestamps[field] = None if value is None else _strict_int(value, field)

        target_end = _advance(origin, family, bars)
        hypothetical_issue = origin + lag
        first_published = timestamps["source_first_published_at_utc"]
        last_revised = timestamps["source_last_revised_at_utc"]
        target_published = timestamps["target_first_published_at_utc"]
        reasons = []
        if origin >= dev_end or target_end >= dev_end or target_end >= reserved:
            reasons.append("OUTSIDE_APPROVED_DEVELOPMENT")
        if hypothetical_issue >= target_end or hypothetical_issue >= dev_end:
            reasons.append("LATE_HYPOTHETICAL_ISSUE")
        if not record["source_window_complete"] or record["source_gap_present"]:
            reasons.append("SOURCE_GAP_OR_INCOMPLETE")
        if first_published is None or last_revised is None:
            reasons.append("SOURCE_PUBLICATION_UNKNOWN")
        elif (
            first_published > last_revised
            or last_revised > hypothetical_issue
            or first_published > hypothetical_issue
        ):
            reasons.append("SOURCE_NOT_KNOWABLE_AT_ISSUE")
        if target_published is None or target_published > asof:
            reasons.append("TARGET_NOT_MATURE_AT_REVIEW")
        elif target_published < target_end or target_published >= dev_end:
            reasons.append("TARGET_PUBLICATION_OUTSIDE_APPROVED_BOUNDARY")

        results.append(
            {
                "schedule_id": record_id,
                "origin_cutoff_utc": origin,
                "hypothetical_issue_utc": hypothetical_issue,
                "target_end_utc": target_end,
                "status": "PROVISIONAL_ELIGIBLE" if not reasons else "EXCLUDED",
                "reasons": reasons,
            }
        )
    provisional = sum(row["status"] == "PROVISIONAL_ELIGIBLE" for row in results)
    return {
        "status": "UNVERIFIED_METADATA_ONLY",
        "scientific_authorization": "NO_RUN",
        "stage7_freeze_authorized": False,
        "horizon": horizon,
        "scheduled_origin_count": len(results),
        "provisionally_eligible_count": provisional,
        "excluded_count": len(results) - provisional,
        "independent_effective_n": "UNKNOWN",
        "source_provenance_authenticated": False,
        "locked_oos_access": False,
        "origins": results,
    }
