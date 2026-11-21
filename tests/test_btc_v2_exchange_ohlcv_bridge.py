"""Synthetic V1 exchange-artifact compatibility tests; no API or locked OOS."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts.btc_v2_exchange_ohlcv_bridge import (
    EXCHANGES,
    _source_digest,
    audit_both_venues,
    exchange_inventory,
)
from scripts.btc_v2_joint_readiness_audit import HORIZON_SOURCE
from scripts.btc_v2_news_evidence import EvidenceError

END = "2026-09-29T00:00:00Z"


def stamp(t: datetime) -> int:
    return int(t.timestamp())


def candle(start: datetime) -> dict:
    return {
        "timestamp": stamp(start),
        "open": 100.0,
        "high": 105.0,
        "low": 95.0,
        "close": 102.0,
        "volume": 3.0,
    }


def prepared(start: datetime, source: int, expected: int) -> dict:
    return {
        **candle(start),
        "is_complete": source == expected,
        "source_bars": source,
        "expected_source_bars": expected,
    }


def make_artifacts(folder: Path) -> tuple[Path, Path]:
    real = folder / "real-data"
    output = folder / "prepared"
    real.mkdir()
    output.mkdir()
    sept = datetime(2026, 9, 25, tzinfo=UTC)
    hour_base = datetime(2026, 9, 27, tzinfo=UTC)
    native_day = [candle(sept + timedelta(days=i)) for i in range(4)]
    native_hour = [candle(hour_base + timedelta(hours=i)) for i in range(4)]
    weekly = [
        prepared(datetime(2026, 9, 21, tzinfo=UTC), 3, 7),
        prepared(datetime(2026, 9, 28, tzinfo=UTC), 1, 7),
    ]
    month = [prepared(datetime(2026, 9, 1, tzinfo=UTC), 4, 30)]
    daily = [prepared(sept + timedelta(days=i), 1, 1) for i in range(4)]
    manifest: dict = {"exchanges": {}}
    for venue in EXCHANGES:
        (real / f"{venue}_hourly.json").write_text(json.dumps(native_hour), encoding="utf-8")
        (real / f"{venue}_daily_native.json").write_text(json.dumps(native_day), encoding="utf-8")
        (real / f"{venue}_hourly_audit.json").write_text(
            json.dumps({"exchange": venue, "rows": 4, "data_sha256": _source_digest(native_hour)}),
            encoding="utf-8",
        )
        tframes = {}
        for family, items in (("1d", daily), ("1w", weekly), ("1mo", month)):
            (output / f"{venue}_{family}.json").write_text(json.dumps(items), encoding="utf-8")
            tframes[family] = {
                "closed_buckets_seen": len(items),
                "data_sha256": _source_digest(items),
            }
        manifest["exchanges"][venue] = {
            "exchange": venue,
            "source_granularity": "native_1d",
            "source_sha256": _source_digest(native_day),
            "timeframes": tframes,
        }
    (output / "prepared_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return real, output


def origins() -> list[dict]:
    return [{"horizon": h, "cutoff_utc": "2026-09-27T03:15:00Z"} for h in sorted(HORIZON_SOURCE)]


class ExchangeBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.real, self.output = make_artifacts(Path(self.temp.name))

    def _report(self, observations: list[dict] | None = None) -> dict:
        return audit_both_venues(
            self.real,
            self.output,
            origins(),
            [] if observations is None else observations,
            approved_development_end_utc=END,
        )

    def test_two_exchange_13_horizon_metadata_without_prices(self):
        report = self._report()
        self.assertEqual(set(report["venues"]), set(EXCHANGES))
        for venue in EXCHANGES:
            item = report["venues"][venue]
            self.assertEqual(len(item["joint_readiness"]["by_horizon"]), 13)
            self.assertFalse(item["source_audit"]["train_eligible"])
            self.assertEqual(item["joint_readiness"]["by_horizon"]["4h"]["origins"], 1)
            self.assertEqual(
                item["joint_readiness"]["by_horizon"]["4h"]["fundamental_any_count"], 0
            )
        self.assertFalse(report["source_first_seen_independently_witnessed"])
        self.assertFalse(report["train_or_stage7_authorized"])
        self.assertEqual(
            report["cross_venue_time_span_by_family"]["1h"]["first_common_closed_bucket_end_utc"],
            "2026-09-27T01:00:00Z",
        )
        self.assertNotIn('"open":', json.dumps(report))
        self.assertNotIn('"close":', json.dumps(report))

    def test_hourly_closes_use_next_hour_not_open(self):
        record = exchange_inventory(
            "bitstamp",
            self.real,
            self.output,
            approved_development_end_utc=END,
        )
        hours = record["technical_buckets"]["1h"]
        self.assertEqual(hours[0]["close_at_utc"], "2026-09-27T01:00:00Z")
        self.assertEqual(hours[-1]["close_at_utc"], "2026-09-27T04:00:00Z")
        self.assertTrue(all(row["is_complete"] for row in hours))

    def test_unfinished_week_and_month_are_excluded_not_relabelled(self):
        record = exchange_inventory(
            "bitstamp", self.real, self.output, approved_development_end_utc=END
        )
        self.assertEqual(record["unclosed_prepared_buckets_excluded"]["1w"], 1)
        self.assertEqual(record["unclosed_prepared_buckets_excluded"]["1mo"], 1)
        self.assertEqual(len(record["technical_buckets"]["1w"]), 1)
        self.assertEqual(record["technical_buckets"]["1w"][0]["is_complete"], False)

    def test_missing_hour_is_reported_as_break_not_fabricated(self):
        path = self.real / "bitstamp_hourly.json"
        rows = json.loads(path.read_text(encoding="utf-8"))
        del rows[1]
        path.write_text(json.dumps(rows), encoding="utf-8")
        audit = self.real / "bitstamp_hourly_audit.json"
        report = json.loads(audit.read_text(encoding="utf-8"))
        report["rows"] = len(rows)
        report["data_sha256"] = _source_digest(rows)
        audit.write_text(json.dumps(report), encoding="utf-8")
        spans = self._report()["venues"]["bitstamp"]["source_audit"]["time_coverage_by_family"]
        self.assertEqual(spans["1h"]["nonconsecutive_bucket_break_count"], 1)
        self.assertEqual(spans["1h"]["closed_bucket_count"], 3)

    def test_source_sha_mismatch_fails_closed(self):
        path = self.real / "bitstamp_hourly_audit.json"
        item = json.loads(path.read_text(encoding="utf-8"))
        item["data_sha256"] = "f" * 64
        path.write_text(json.dumps(item), encoding="utf-8")
        with self.assertRaisesRegex(EvidenceError, "digest mismatch"):
            self._report()

    def test_prepared_completeness_mismatch_fails_closed(self):
        path = self.output / "bitstamp_1w.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data[0]["is_complete"] = True
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(EvidenceError, "counts or completeness"):
            self._report()

    def test_prepared_source_count_mismatch_fails_closed(self):
        path = self.output / "bitstamp_1w.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data[0]["source_bars"] = 2
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(EvidenceError):
            self._report()

    def test_unapproved_future_raw_candle_fails(self):
        path = self.real / "bitfinex_daily_native.json"
        rows = json.loads(path.read_text(encoding="utf-8"))
        rows.append(candle(datetime(2026, 9, 29, tzinfo=UTC)))
        path.write_text(json.dumps(rows), encoding="utf-8")
        with self.assertRaisesRegex(EvidenceError, "unapproved development"):
            self._report()

    def test_future_origin_not_allowed(self):
        rows = origins()
        rows[0]["cutoff_utc"] = "2026-10-02T00:00:00Z"
        with self.assertRaisesRegex(EvidenceError, "origins exceed"):
            audit_both_venues(
                self.real,
                self.output,
                rows,
                [],
                approved_development_end_utc=END,
            )

    def test_duplicate_hour_and_bad_venue_rejected(self):
        path = self.real / "bitstamp_hourly.json"
        rows = json.loads(path.read_text(encoding="utf-8"))
        rows.append(rows[-1])
        path.write_text(json.dumps(rows), encoding="utf-8")
        with self.assertRaisesRegex(EvidenceError, "duplicate"):
            self._report()
        with self.assertRaises(EvidenceError):
            exchange_inventory("unknown", self.real, self.output, approved_development_end_utc=END)

    def test_prepared_sha_mismatch_detected_before_audit(self):
        path = self.output / "bitfinex_1mo.json"
        rows = json.loads(path.read_text(encoding="utf-8"))
        rows[0]["high"] = 107.0
        path.write_text(json.dumps(rows), encoding="utf-8")
        with self.assertRaisesRegex(EvidenceError, "digest mismatch"):
            self._report()


if __name__ == "__main__":
    unittest.main()
