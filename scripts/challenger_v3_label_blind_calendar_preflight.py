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


def _strict_timestamp(value: object, label: str) -> int:
    """Require an exact UTC epoch integer representable by Python datetime."""
    timestamp = _strict_int(value, label)
    _utc(timestamp)
    return timestamp


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
    result = timestamp + bars * seconds
    _utc(result)  # Reject hourly/daily/weekly overflow like monthly already does.
    return result


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
    first = _strict_timestamp(plan["first_origin_utc"], "first_origin_utc")
    stop = _strict_timestamp(plan["stop_origin_utc"], "stop_origin_utc")
    lag = _strict_int(plan["hypothetical_issue_lag_seconds"], "issue lag")
    asof = _strict_timestamp(plan["review_asof_utc"], "review as-of")
    dev_end = _strict_timestamp(plan["approved_dev_end_exclusive_utc"], "dev end")
    reserved = _strict_timestamp(plan["reserved_start_utc"], "reserved start")
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
    for expected, record in zip(origins, records, strict=True):
        if not isinstance(record, Mapping) or set(record) != RECORD_KEYS:
            raise ValueError("Rejected non-metadata, price, outcome or unknown fields")
        # Never echo arbitrary caller text, which could carry prices or results.
        # Identity is deterministically bound to both frozen plan horizon and
        # the strictly scheduled origin: swapping otherwise valid IDs fails.
        record_id = f"origin:{horizon}:{expected}"
        if type(record["schedule_id"]) is not str or record["schedule_id"] != record_id:
            raise ValueError("Schedule ID does not match fixed horizon/origin identity")
        origin = _strict_timestamp(record["origin_cutoff_utc"], "origin cutoff")
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
            timestamps[field] = None if value is None else _strict_timestamp(value, field)

        target_end = _advance(origin, family, bars)
        hypothetical_issue = _strict_timestamp(origin + lag, "hypothetical issue")
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


# Optional synthetic-only review for the input bytes actually claimed at an
# issuance instant. This is NOT an exchange timestamp or version authenticator.
ASOF_PLAN_KEYS = frozenset({"origin_cutoff_utc", "forecast_issued_at_utc", "forecast_target_end_utc"})
ASOF_INPUT_KEYS = frozenset(
    {
        "kind",
        "bar_open_utc",
        "bar_end_utc",
        "first_observed_at_utc",
        "selected_version_observed_at_utc",
        "selected_version_superseded_at_utc",
    }
)
ASOF_KINDS = frozenset({"feature_bar", "training_label"})
MAX_ASOF_INPUTS = 512


def audit_claimed_asof_input_versions(
    plan: Mapping[str, object], inputs: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    """Fail closed on late source/label versions using claimed timestamps only.

    An earlier authentic version remains usable after a *future* correction;
    corrected final bytes cannot be substituted for the old version. Actual
    vintage bytes, content digests, clock integrity and source authorization
    require separate independent operator evidence under Issue #81 A1-A6.
    """
    if not isinstance(plan, Mapping) or set(plan) != ASOF_PLAN_KEYS:
        raise ValueError("Exact as-of issuance plan metadata required")
    origin = _strict_timestamp(plan["origin_cutoff_utc"], "origin cutoff")
    issued = _strict_timestamp(plan["forecast_issued_at_utc"], "forecast issuance")
    target_end = _strict_timestamp(plan["forecast_target_end_utc"], "forecast target end")
    if origin <= 0 or not origin < issued < target_end:
        raise ValueError("Forecast must be issued after origin and before future target end")
    if (
        not isinstance(inputs, Sequence)
        or isinstance(inputs, (str, bytes))
        or not 0 < len(inputs) <= MAX_ASOF_INPUTS
    ):
        raise ValueError("Nonempty bounded as-of metadata sequence required")

    seen: set[tuple[str, int]] = set()
    kinds: set[str] = set()
    results: list[dict[str, object]] = []
    for index, record in enumerate(inputs):
        if not isinstance(record, Mapping) or set(record) != ASOF_INPUT_KEYS:
            raise ValueError("Only closed-schema non-outcome as-of metadata allowed")
        kind = record["kind"]
        if type(kind) is not str or kind not in ASOF_KINDS:
            raise ValueError("Unknown as-of input kind")
        kinds.add(kind)
        opening = _strict_timestamp(record["bar_open_utc"], "bar opening")
        ending = _strict_timestamp(record["bar_end_utc"], "bar end")
        if not 0 < opening < ending <= origin:
            raise ValueError("As-of input bar must close by the forecast origin")
        identity = (kind, ending)
        if identity in seen:
            raise ValueError("Duplicate kind/end identity in claimed as-of input")
        seen.add(identity)

        stamps: dict[str, int | None] = {}
        for key in (
            "first_observed_at_utc",
            "selected_version_observed_at_utc",
            "selected_version_superseded_at_utc",
        ):
            value = record[key]
            stamps[key] = None if value is None else _strict_timestamp(value, key)
        first = stamps["first_observed_at_utc"]
        selected = stamps["selected_version_observed_at_utc"]
        superseded = stamps["selected_version_superseded_at_utc"]
        if superseded is not None and (selected is None or superseded <= selected):
            raise ValueError("Contradictory version supersession chronology")

        gaps: list[str] = []
        if first is None or selected is None:
            gaps.append("SOURCE_OR_LABEL_VINTAGE_UNKNOWN")
        elif first < ending or selected < ending or first > selected:
            gaps.append("CONTRADICTORY_VINTAGE_CHRONOLOGY")
        elif first > issued or selected > issued:
            gaps.append("VERSION_NOT_KNOWN_AT_ISSUE")
        if superseded is not None and superseded <= issued:
            gaps.append("SELECTED_VERSION_ALREADY_SUPERSEDED")
        results.append(
            {
                "index": index,
                "kind": kind,
                "status": "BLOCKED" if gaps else "METADATA_CONSISTENT_UNVERIFIED",
                "gaps": gaps,
            }
        )

    missing_kinds = sorted(ASOF_KINDS - kinds)
    blocked = bool(missing_kinds) or any(row["status"] == "BLOCKED" for row in results)
    return {
        "status": "BLOCKED" if blocked else "UNVERIFIED_ASOF_METADATA_ONLY",
        "scientific_authorization": "NO_RUN",
        "stage7_freeze_authorized": False,
        "real_source_vintages_authenticated": False,
        "independent_custody_verified": False,
        "required_input_kinds_missing": missing_kinds,
        "input_count": len(results),
        "blocked_input_count": sum(row["status"] == "BLOCKED" for row in results),
        "inputs": results,
    }
