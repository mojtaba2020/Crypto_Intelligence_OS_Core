#!/usr/bin/env python3
"""Bounded, label-blind Stage-6 source-only BTC multi-horizon coverage check.

Only use with an operator-reviewed development interval. An input cutoff is an
operator declaration, not an independently witnessed custody/split approval.
Does not download or score models; the dedicated workflow fetches market data
using the existing V1 exchange adapters and never runs the locked judge.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts.multitimeframe_lab_v1 import SPECS
from scripts.resample_multitimeframe_ohlcv import (
    _bucket_end,
    _bucket_start,
    coverage_metadata_identity,
    source_data_identity,
)

EXCHANGES = ("bitstamp", "bitfinex")
FAMILIES = ("1h", "1d", "1w", "1mo")
MAX_WINDOW_DAYS = 120
EARLIEST_DUAL_VENUE_PILOT = datetime(2014, 1, 1, tzinfo=UTC)


def utc_timestamp(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith(("Z", "+00:00")):
        raise ValueError("use UTC YYYY-MM-DDTHH:MM:SSZ")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timezone required")
    return dt.astimezone(UTC)


def validate_window(
    start: str, end: str, approved_development_end: str, *, now: datetime | None = None
) -> dict:
    """Hard-stop before ANY network activity or loading market values."""
    a, b, c = (utc_timestamp(x) for x in (start, end, approved_development_end))
    clock = now if now is not None else datetime.now(UTC)
    if clock.tzinfo is None:
        raise ValueError("evaluation clock must be timezone-aware")
    clock = clock.astimezone(UTC)
    if any(value.time() != datetime.min.time() for value in (a, b, c)):
        raise ValueError("source-only collection requires UTC midnight boundaries")
    if a < EARLIEST_DUAL_VENUE_PILOT:
        raise ValueError("dual-venue pilot begins 2014-01-01; earlier Bitstamp is separate")
    if not a < b <= c:
        raise ValueError("interval must end before the approved development boundary")
    if not timedelta(days=2) <= b - a <= timedelta(days=MAX_WINDOW_DAYS):
        raise ValueError("bounded pilot interval must be 2 to 120 days")
    if b > clock - timedelta(days=2):
        raise ValueError("do not collect incomplete or recent target intervals")
    return {
        "status": "STAGE6_SOURCE_ONLY_OPERATOR_DECLARED_DEV_WINDOW",
        "requested_start_utc": a.isoformat().replace("+00:00", "Z"),
        "requested_end_utc": b.isoformat().replace("+00:00", "Z"),
        "operator_declared_dev_end_utc": c.isoformat().replace("+00:00", "Z"),
        "outside_operator_boundaries_rejected": True,
        "independent_dev_boundary_custody_verified": False,
        "locked_outcomes_inspected_by_this_script": False,
        "science_or_training_authorized": False,
    }


def _load_json(path: Path) -> object:
    if path.stat().st_size > 50_000_000:
        raise ValueError("source file exceeds bounded size")
    return json.loads(path.read_text(encoding="utf-8"))


def _source_buckets(
    path: Path,
    family: str,
    expected_sha: str,
    end: datetime,
    *,
    expected_coverage_sha: str | None = None,
) -> tuple[list[tuple[datetime, bool]], str]:
    rows = _load_json(path)
    if not isinstance(rows, list):
        raise ValueError("OHLCV source must be a list")
    sha = source_data_identity(rows)
    if sha != expected_sha:
        raise ValueError("data hash mismatch")
    if family != "1h" and not expected_coverage_sha:
        raise ValueError("missing prepared coverage metadata digest")
    buckets: list[tuple[datetime, bool]] = []
    seen: set[int] = set()
    last: int | None = None
    for row in rows:
        timestamp = row["timestamp"]
        if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
            raise ValueError("non-numeric timestamp")
        ts = int(timestamp)
        if ts != timestamp or ts in seen or (last is not None and ts <= last):
            raise ValueError("timestamps out of order, duplicate or fractional")
        seen.add(ts)
        last = ts
        open_time = datetime.fromtimestamp(ts, UTC)
        if open_time >= end:
            raise ValueError("source row starts outside approved interval")
        if open_time.minute or open_time.second or open_time.microsecond:
            raise ValueError("source not hour-aligned")
        if family != "1h" and open_time.hour:
            raise ValueError("prepared buckets not UTC-day aligned")
        if family == "1w" and open_time.weekday() != 0:
            raise ValueError("weekly bucket not Monday-aligned")
        if family == "1mo" and open_time.day != 1:
            raise ValueError("monthly bucket not calendar aligned")
        closed = (
            open_time + timedelta(hours=1) if family == "1h" else _bucket_end(open_time, family)
        )
        complete = True if family == "1h" else row.get("is_complete")
        if type(complete) is not bool:
            raise ValueError("malformed complete flag")
        if family != "1h":
            count = row.get("source_bars")
            expected = row.get("expected_source_bars")
            actual_expected = (closed - open_time).days
            if (
                type(count) is not int
                or type(expected) is not int
                or expected != actual_expected
                or not 0 <= count <= expected
            ):
                raise ValueError("invalid prepared bar counts")
            if complete != (count == expected):
                raise ValueError("inconsistent prepared completeness")
        if closed > end:
            continue
        buckets.append((closed, complete))
    if family != "1h" and coverage_metadata_identity(rows) != expected_coverage_sha:
        raise ValueError("coverage metadata hash mismatch")
    return buckets, sha


def _family_summary(buckets: list[tuple[datetime, bool]], family: str, end: datetime) -> dict:
    sequence: list[tuple[datetime, bool]] = []
    breaks = 0
    previous: datetime | None = None
    for close, complete in buckets:
        if previous is not None:
            next_expected = (
                previous + timedelta(hours=1) if family == "1h" else _bucket_end(previous, family)
            )
            if close != next_expected:
                breaks += 1
        previous = close
        sequence.append((close, complete))
    valid = 0
    for i, (close, complete) in enumerate(reversed(sequence)):
        if not complete:
            break
        if i:
            next_expected = (
                close + timedelta(hours=1) if family == "1h" else _bucket_end(close, family)
            )
            if next_expected != sequence[len(sequence) - i][0]:
                break
        valid += 1
    last_end = sequence[-1][0] if sequence else None
    freshness = (
        last_end is not None
        and last_end <= end
        and (
            end
            < (last_end + timedelta(hours=1) if family == "1h" else _bucket_end(last_end, family))
            or end == last_end
        )
    )
    return {
        "closed_bucket_count": len(sequence),
        "first_closed_utc": sequence[0][0].isoformat() if sequence else None,
        "last_closed_utc": last_end.isoformat() if last_end else None,
        "incomplete_bucket_count": sum(not complete for _, complete in sequence),
        "source_gap_breaks": breaks,
        "latest_consecutive_complete_bars": valid,
        "latest_bar_fresh_for_dev_cutoff": freshness,
    }


def _calendar_closes(start: datetime, end: datetime, family: str) -> list[datetime]:
    """Close times of full UTC buckets contained in the requested interval."""
    cursor = start if family == "1h" else _bucket_start(int(start.timestamp()), family)
    closes = []
    while cursor < end:
        following = cursor + timedelta(hours=1) if family == "1h" else _bucket_end(cursor, family)
        if cursor >= start and following <= end:
            closes.append(following)
        cursor = following
    return closes


def _fundamental_origin_counts(audit: dict) -> dict:
    """Read PR #117's per-origin union, including its non-displayed 12h row."""
    if not isinstance(audit, dict) or audit.get("status") != "STAGE6_LABEL_BLIND_UNATTESTED_COVERAGE_ONLY":
        raise ValueError("expected a PR #117 fundamental coverage audit")
    rows = audit.get("horizons")
    if not isinstance(rows, dict):
        raise ValueError("missing fundamental audit horizons")
    counts = {}
    for label, row in rows.items():
        if not isinstance(row, dict):
            raise ValueError("invalid fundamental audit row")
        checked = row.get("scheduled_origins")
        eligible = row.get("origins_with_any_metric")
        if type(checked) is not int or type(eligible) is not int or not 0 <= eligible <= checked:
            raise ValueError("invalid fundamental origin counts")
        counts[label] = (eligible, checked)
    total = audit.get("input_origin_count")
    if type(total) is not int or total != sum(checked for _, checked in counts.values()):
        raise ValueError("fundamental audit origin total mismatch")
    return counts


def requested_horizon_readiness(
    window: dict, matched: dict | None = None, fundamental_audit: dict | None = None
) -> dict:
    """Describe the requested horizons in units of complete source candles."""
    start = utc_timestamp(window["requested_start_utc"])
    end = utc_timestamp(window["requested_end_utc"])
    capacities = {family: len(_calendar_closes(start, end, family)) for family in FAMILIES}
    rows = {}
    fundamental_counts = _fundamental_origin_counts(fundamental_audit) if fundamental_audit is not None else {}
    labels = "1h 2h 3h 4h 1d 2d 3d 1w 2w 3w 1mo 3mo 6mo 1y".split()
    for spec in SPECS:
        if spec.label not in labels:
            continue
        family = spec.source_timeframe
        expected = capacities[family]
        # Coverage and run length are identical for horizons using the same source candles.
        row = {
            "source_timeframe": family,
            "classification": "پژوهشی" if spec.promotion_eligible else "اکتشافی",
            "expected_bars": expected,
            "minimum_history_bars": spec.minimum_history_bars,
            "minimum_deficit_even_with_full_coverage": max(0, spec.minimum_history_bars - expected),
            "price_status": "اندازه‌گیری نشده",
            "fundamental_status": "اندازه‌گیری نشده",
            "fundamental_checked_origins": None,
            "fundamental_eligible_origins": None,
            "complete_shared_bars": None,
            "longest_shared_run_bars": None,
            "missing_or_incomplete_shared_bars": None,
            "history_deficit_bars": None,
        }
        # The audit has its own schedule. These counts do not establish an
        # intersection with the price window or independently attest first-seen dates.
        eligible, checked = fundamental_counts.get(spec.label, (0, 0))
        if checked:
            row.update(
                fundamental_status=f"{eligible} از {checked} زمان بررسی‌شده",
                fundamental_checked_origins=checked,
                fundamental_eligible_origins=eligible,
            )
        if matched is not None:
            metrics = matched[family]
            complete = metrics["complete_buckets_on_both_venues"]
            longest = metrics["longest_consecutive_complete_buckets_on_both_venues"]
            row.update(
                price_status="محاسبه از فایل‌های ورودی",
                complete_shared_bars=complete,
                longest_shared_run_bars=longest,
                missing_or_incomplete_shared_bars=expected - complete,
                history_deficit_bars=max(0, spec.minimum_history_bars - longest),
            )
        rows[spec.label] = row
    return rows


def build_metadata_report(
    real_dir: Path, prepared_dir: Path, window: dict, fundamental_audit: dict | None = None
) -> dict:
    start = utc_timestamp(window["requested_start_utc"])
    end = utc_timestamp(window["requested_end_utc"])
    manifest = _load_json(real_dir / "manifest.json")
    prepared = _load_json(prepared_dir / "prepared_manifest.json")
    if not isinstance(manifest, dict) or not isinstance(prepared, dict):
        raise ValueError("missing upstream V1 source manifests")
    details: dict[str, dict] = {}
    calendars = {family: _calendar_closes(start, end, family) for family in FAMILIES}
    common = {family: set(grid) for family, grid in calendars.items()}
    for exchange in EXCHANGES:
        hourly = manifest["exchanges"][exchange]
        daily = prepared["exchanges"][exchange]
        if hourly.get("exchange") != exchange or daily.get("exchange") != exchange:
            raise ValueError("manifest exchange mismatch")
        if daily.get("source_granularity") != "native_1d":
            raise ValueError("missing or invalid native daily source granularity")
        native_daily_sha = daily.get("source_sha256")
        if not isinstance(native_daily_sha, str) or len(native_daily_sha) != 64:
            raise ValueError("missing native daily source SHA-256")
        source = {}
        lineage = {}
        family_summaries = {}
        for family in FAMILIES:
            if family == "1h":
                path = real_dir / f"{exchange}_hourly.json"
                identity = hourly["data_sha256"]
            else:
                path = prepared_dir / f"{exchange}_{family}.json"
                identity = daily["timeframes"][family]["data_sha256"]
            coverage_sha = (
                None
                if family == "1h"
                else daily["timeframes"][family].get("coverage_metadata_sha256")
            )
            buckets, digest = _source_buckets(
                path, family, identity, end, expected_coverage_sha=coverage_sha
            )
            grid = calendars[family]
            full_closes = set(grid)
            if family in {"1h", "1d"} and any(close <= start for close, _ in buckets):
                raise ValueError("source row starts outside approved interval")
            buckets = [(close, complete) for close, complete in buckets if close in full_closes]
            complete_closes = {close for close, complete in buckets if complete}
            common[family].intersection_update(complete_closes)
            family_summaries[family] = {
                **_family_summary(buckets, family, end),
                "expected_closed_bucket_count": len(grid),
                "missing_closed_bucket_count": len(grid) - len(buckets),
                "complete_closed_bucket_count": len(complete_closes),
            }
            source[family] = digest
            # A candle timestamp denotes its market bucket, not when a collector
            # first observed or published the payload. Never infer source custody.
            lineage[family] = {
                "source_path_kind": (
                    "native_exchange_hourly"
                    if family == "1h"
                    else "native_exchange_daily_calendar_aggregation"
                ),
                "native_input_granularity": "1h" if family == "1h" else "1d",
                "native_input_ohlcv_sha256": (
                    hourly["data_sha256"] if family == "1h" else native_daily_sha
                ),
                "family_ohlcv_sha256": digest,
                "family_coverage_metadata_sha256": coverage_sha,
                "retrieved_at_utc": None,
                "historical_first_observed_at_utc": None,
                "historical_published_at_utc": None,
                "revision_vintage_id": None,
                "independent_custody_verified": False,
                "source_license_verified": False,
            }
        horizons = {}
        for spec in SPECS:
            if not spec.promotion_eligible:
                continue
            base = family_summaries[spec.source_timeframe]
            ready = (
                base["latest_consecutive_complete_bars"] >= spec.minimum_history_bars
                and base["latest_bar_fresh_for_dev_cutoff"]
            )
            horizons[spec.label] = {
                "minimum_bars": spec.minimum_history_bars,
                "eligible_technical_origin_at_end": bool(ready),
                "fundamental_as_of_evidence_provided": False,
                "eligible_for_training_or_promotion": False,
            }
        if len(horizons) != 13:
            raise ValueError("diverged from 13-horizon charter")
        details[exchange] = {
            "source_sha256_by_family": source,
            "source_lineage_by_family": lineage,
            "technical_family_coverage": family_summaries,
            "one_origin_per_horizon_at_dev_end": horizons,
        }
    matched = {}
    for spec in SPECS:
        if not spec.promotion_eligible:
            continue
        family = spec.source_timeframe
        streak = 0
        longest_streak = 0
        origins = 0
        for close in calendars[family]:
            streak = streak + 1 if close in common[family] else 0
            longest_streak = max(longest_streak, streak)
            if streak >= spec.minimum_history_bars:
                origins += 1
        matched[spec.label] = {
            "source_timeframe": family,
            "expected_closed_buckets": len(calendars[family]),
            "complete_buckets_on_both_venues": len(common[family]),
            "longest_consecutive_complete_buckets_on_both_venues": longest_streak,
            "common_closes_with_minimum_history": origins,
        }
    return {
        "status": "STAGE6_E2_TWO_VENUE_SOURCE_ONLY_METADATA_REPORT",
        "development_window": window,
        "venues": details,
        "requested_horizon_readiness": requested_horizon_readiness(window, matched, fundamental_audit),
        "two_venue_calendar_coverage_by_horizon": matched,
        "market_values_checked_for_integrity_only": True,
        "source_is_real_market_data_independently_verified": False,
        "historical_first_seen_independently_verified": False,
        "protected_oos_boundary_independently_verified": False,
        "eligible_for_model_training_or_stage7": False,
        "real_fundamental_observations_supplied": False,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--approved-development-end", required=True)
    p.add_argument("--real-dir", type=Path)
    p.add_argument("--prepared-dir", type=Path)
    p.add_argument("--fundamental-audit", type=Path,
                   help="PR #117 coverage JSON; counts describe its own forecast schedule")
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    window = validate_window(args.start, args.end, args.approved_development_end)
    if (args.real_dir is None) != (args.prepared_dir is None):
        p.error("both real and prepared directories are required for report")
    audit = None
    if args.fundamental_audit is not None:
        if args.fundamental_audit.resolve() == args.output.resolve():
            p.error("fundamental audit and output must be different paths")
        audit = _load_json(args.fundamental_audit)
        if not isinstance(audit, dict):
            p.error("fundamental audit must be a JSON object")
    report = (
        build_metadata_report(args.real_dir, args.prepared_dir, window, audit)
        if args.real_dir is not None and args.prepared_dir is not None
        else {**window, "requested_horizon_readiness": requested_horizon_readiness(window, fundamental_audit=audit)}
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    args.output.write_text(payload + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

