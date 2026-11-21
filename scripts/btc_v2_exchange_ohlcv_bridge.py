"""E2: translate V1 real Bitstamp/Bitfinex OHLCV artifacts to label-free readiness.

Input is the existing V1 real-data and gap-safe prepared output, NOT the V1
workflow itself (which also touches a reserved locked test). The operator must
supply a preauthorized development-only UTC endpoint. Do not use protected OOS.
Price values are checked only for source integrity; outputs contain no prices,
outcomes, model scores, or claims of first-known historical source custody.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from bisect import bisect_left
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts.btc_v2_joint_readiness_audit import audit_joint_readiness
from scripts.btc_v2_news_evidence import EvidenceError, utc

EXCHANGES = ("bitstamp", "bitfinex")
FAMILIES = ("1h", "1d", "1w", "1mo")
INTERVALS = {"1h": 3600, "1d": 86400}
SOURCE_KEYS = ("timestamp", "open", "high", "low", "close", "volume")
MAX_FILE_BYTES = 45_000_000
MAX_ROWS = 150_000


def _start(raw: object, family: str) -> datetime:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise EvidenceError("non-numeric source timestamp")
    if not math.isfinite(raw) or int(raw) != raw:
        raise EvidenceError("non-integral source timestamp")
    try:
        start = datetime.fromtimestamp(int(raw), UTC)
    except (ValueError, OverflowError, OSError) as exc:
        raise EvidenceError("timestamp outside supported range") from exc
    if start.minute or start.second or start.microsecond:
        raise EvidenceError("source bucket not hour-aligned")
    if family != "1h" and start.hour:
        raise EvidenceError("daily/weekly/monthly bucket must start at UTC midnight")
    if family == "1w" and start.weekday() != 0:
        raise EvidenceError("weekly bucket must begin Monday UTC")
    if family == "1mo" and start.day != 1:
        raise EvidenceError("monthly bucket must begin on first day UTC")
    return start


def _end(start: datetime, family: str) -> datetime:
    if family == "1mo":
        return (
            start.replace(year=start.year + 1, month=1)
            if start.month == 12
            else start.replace(month=start.month + 1)
        )
    return start + {
        "1h": timedelta(hours=1),
        "1d": timedelta(days=1),
        "1w": timedelta(days=7),
    }[family]


def _z(at: datetime) -> str:
    return at.isoformat().replace("+00:00", "Z")


def _read(path: Path) -> object:
    if path.stat().st_size > MAX_FILE_BYTES:
        raise EvidenceError("source artifact exceeds bounded size")
    return json.loads(path.read_text(encoding="utf-8"))


def _rows(raw: object) -> list[dict]:
    if not isinstance(raw, list) or len(raw) > MAX_ROWS:
        raise EvidenceError("source artifact must be a bounded list")
    if not all(isinstance(row, dict) for row in raw):
        raise EvidenceError("each source record must be a mapping")
    return raw


def _source_digest(rows: list[dict]) -> str:
    # Exact normalization used by V1's source_data_identity; this verifies
    # bytes-as-values, NOT independent exchange authenticity or first-seen time.
    normalized = []
    for row in rows:
        if any(key not in row for key in SOURCE_KEYS):
            raise EvidenceError("missing OHLCV fields")
        values = {key: float(row[key]) for key in SOURCE_KEYS[1:]}
        if not all(math.isfinite(value) for value in values.values()):
            raise EvidenceError("nonfinite OHLCV value")
        if min(values[name] for name in ("open", "high", "low", "close")) < 0:
            raise EvidenceError("negative price")
        if values["volume"] < 0:
            raise EvidenceError("negative volume")
        if values["high"] < max(values["open"], values["low"], values["close"]):
            raise EvidenceError("inconsistent high")
        if values["low"] > min(values["open"], values["high"], values["close"]):
            raise EvidenceError("inconsistent low")
        normalized.append({"timestamp": int(row["timestamp"]), **values})
    normalized.sort(key=lambda item: item["timestamp"])
    raw = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _verified_source(
    rows: list[dict], expected_sha: str, family: str, cutoff: datetime
) -> tuple[list[datetime], str]:
    if not isinstance(expected_sha, str) or len(expected_sha) != 64:
        raise EvidenceError("missing or malformed V1 source identity")
    starts = [_start(row["timestamp"], family) for row in rows]
    if any(curr <= prev for prev, curr in zip(starts, starts[1:])):
        raise EvidenceError("duplicate, descending or reordered source timestamps")
    if any(_end(start, family) > cutoff for start in starts):
        raise EvidenceError("input contains an unclosed or unapproved development period")
    actual = _source_digest(rows)
    if actual != expected_sha:
        raise EvidenceError("V1 source digest mismatch")
    return starts, actual


def _prepared_bucket_meta(
    rows: list[dict], family: str, cutoff: datetime, native_starts: list[datetime]
) -> tuple[list[dict], int]:
    result: list[dict] = []
    dropped_unclosed = 0
    previous: datetime | None = None
    for row in rows:
        start = _start(row["timestamp"], family)
        if previous is not None and start <= previous:
            raise EvidenceError("duplicate or descending prepared start")
        previous = start
        end = _end(start, family)
        expected = int((end - start).total_seconds() / 86400)
        num = row.get("source_bars")
        size = row.get("expected_source_bars")
        flag = row.get("is_complete")
        if (
            type(num) is not int
            or type(size) is not int
            or type(flag) is not bool
            or num < 0
            or num > expected
            or size != expected
            or flag != (num == expected)
        ):
            raise EvidenceError("invalid V1 prepared bar counts or completeness")
        left = bisect_left(native_starts, start)
        right = bisect_left(native_starts, end)
        if num != right - left:
            raise EvidenceError("prepared source_bars disagree with native daily input")
        if end > cutoff:
            dropped_unclosed += 1
            continue
        result.append({"close_at_utc": _z(end), "is_complete": flag})
    return result, dropped_unclosed


def exchange_inventory(
    exchange: str,
    real_dir: Path,
    prepared_dir: Path,
    *,
    approved_development_end_utc: str,
) -> dict:
    """Validate V1 artifacts and return price-free hourly/daily/weekly/monthly metadata."""
    if exchange not in EXCHANGES:
        raise EvidenceError("unsupported exchange")
    cutoff = utc(approved_development_end_utc)
    audit = _read(real_dir / f"{exchange}_hourly_audit.json")
    manifest = _read(prepared_dir / "prepared_manifest.json")
    if not isinstance(audit, dict) or not isinstance(manifest, dict):
        raise EvidenceError("V1 provenance manifests must be objects")
    if audit.get("exchange") != exchange:
        raise EvidenceError("V1 hourly audit exchange mismatch")
    record = manifest.get("exchanges", {}).get(exchange, {})
    if record.get("exchange") != exchange or record.get("source_granularity") != "native_1d":
        raise EvidenceError("V1 prepared exchange or granularity mismatch")
    hour = _rows(_read(real_dir / f"{exchange}_hourly.json"))
    day = _rows(_read(real_dir / f"{exchange}_daily_native.json"))
    hour_starts, hourly_digest = _verified_source(
        hour, audit.get("data_sha256"), "1h", cutoff
    )
    day_starts, daily_digest = _verified_source(
        day, record.get("source_sha256"), "1d", cutoff
    )
    if audit.get("rows") != len(hour):
        raise EvidenceError("V1 hourly row count mismatch")
    buckets = {
        "1h": [{"close_at_utc": _z(_end(t, "1h")), "is_complete": True} for t in hour_starts]
    }
    dropped: dict[str, int] = {}
    data_digests = {"1h": hourly_digest, "native_1d": daily_digest}
    for family in FAMILIES[1:]:
        dataset = _rows(_read(prepared_dir / f"{exchange}_{family}.json"))
        info = record.get("timeframes", {}).get(family, {})
        starts, data_digests[family] = _verified_source(
            dataset, info.get("data_sha256"), family, cutoff
        ) if family == "1d" else _verified_prepared(dataset, info, family)
        del starts  # All downstream joins use source counts, never prices.
        buckets[family], dropped[family] = _prepared_bucket_meta(
            dataset, family, cutoff, day_starts
        )
    return {
        "exchange": exchange,
        "technical_buckets": buckets,
        "source_sha256_by_family": data_digests,
        "approved_development_end_utc": _z(cutoff),
        "unclosed_prepared_buckets_excluded": dropped,
        "source_vintages_independently_attested": False,
        "train_eligible": False,
    }


def _verified_prepared(
    rows: list[dict], info: dict, family: str
) -> tuple[list[datetime], str]:
    starts = [_start(row["timestamp"], family) for row in rows]
    if any(curr <= prev for prev, curr in zip(starts, starts[1:])):
        raise EvidenceError("duplicate or descending prepared timestamps")
    if info.get("closed_buckets_seen") != len(rows):
        raise EvidenceError("V1 prepared bucket count mismatch")
    digest = _source_digest(rows)
    if digest != info.get("data_sha256"):
        raise EvidenceError("V1 prepared source digest mismatch")
    return starts, digest


def audit_both_venues(
    real_dir: Path,
    prepared_dir: Path,
    origins: list[dict],
    observations: list[dict],
    *,
    approved_development_end_utc: str,
) -> dict:
    cutoff = utc(approved_development_end_utc)
    if any(utc(origin["cutoff_utc"]) > cutoff for origin in origins):
        raise EvidenceError("forecast origins exceed approved development cutoff")
    reports: dict[str, dict] = {}
    for exchange in EXCHANGES:
        inventory = exchange_inventory(
            exchange,
            real_dir,
            prepared_dir,
            approved_development_end_utc=approved_development_end_utc,
        )
        result = audit_joint_readiness(
            {
                "origins": origins,
                "observations": observations,
                "technical_buckets": inventory["technical_buckets"],
            }
        )
        del inventory["technical_buckets"]  # Do not publish full time-series metadata.
        reports[exchange] = {"source_audit": inventory, "joint_readiness": result}
    return {
        "status": "STAGE6_TWO_EXCHANGE_RECONSTRUCTED_E2_FEASIBILITY_ONLY",
        "venues": reports,
        "official_13_horizons": True,
        "source_first_seen_independently_witnessed": False,
        "locked_test_read_or_used": False,
        "train_or_stage7_authorized": False,
        "no_live_download_or_costly_workflow_triggered": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--real-dir", type=Path, required=True)
    parser.add_argument("--prepared-dir", type=Path, required=True)
    parser.add_argument("--origins-json", type=Path, required=True)
    parser.add_argument("--fundamentals-json", type=Path)
    parser.add_argument("--approved-development-end-utc", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    origin_input = _read(args.origins_json)
    if not isinstance(origin_input, dict) or set(origin_input) != {"origins"}:
        raise EvidenceError("origin file must contain only origins")
    fundamentals = (
        _read(args.fundamentals_json) if args.fundamentals_json else {"observations": []}
    )
    if not isinstance(fundamentals, dict) or set(fundamentals) != {"observations"}:
        raise EvidenceError("fundamental input must contain only observations")
    report = audit_both_venues(
        args.real_dir,
        args.prepared_dir,
        origin_input["origins"],
        fundamentals["observations"],
        approved_development_end_utc=args.approved_development_end_utc,
    )
    if args.output.resolve() == args.origins_json.resolve():
        raise EvidenceError("output may not overwrite inputs")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temp = args.output.with_name(args.output.name + ".tmp")
    try:
        temp.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temp.replace(args.output)
    finally:
        temp.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
