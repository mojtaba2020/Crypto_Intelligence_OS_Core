"""Synthetic-only Stage-6 E2 source collector safety and 13-horizon audit."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts.e2_source_only_coverage_v1 import (
    EXCHANGES,
    build_metadata_report,
    validate_window,
)
from scripts.resample_multitimeframe_ohlcv import source_data_identity

START = "2020-01-01T00:00:00Z"
END = "2020-01-04T00:00:00Z"
APPROVED = "2020-02-01T00:00:00Z"
CLOCK = datetime(2026, 11, 20, tzinfo=UTC)


def bar(day: datetime) -> dict:
    return {
        "timestamp": int(day.timestamp()),
        "open": 100.0,
        "high": 102.0,
        "low": 99.0,
        "close": 101.0,
        "volume": 3.0,
    }


def prepared(start: datetime, count: int, expected: int) -> dict:
    return {
        **bar(start),
        "source_bars": count,
        "expected_source_bars": expected,
        "is_complete": count == expected,
    }


def fixture(path: Path) -> tuple[Path, Path]:
    real = path / "real-data"
    prepped = path / "prepared"
    real.mkdir()
    prepped.mkdir()
    date = datetime(2020, 1, 1, tzinfo=UTC)
    hourly = [bar(date + timedelta(hours=i)) for i in range(72)]
    daily = [prepared(date + timedelta(days=i), 1, 1) for i in range(3)]
    weekly = [prepared(datetime(2019, 12, 30, tzinfo=UTC), 3, 7)]
    monthly = [prepared(datetime(2020, 1, 1, tzinfo=UTC), 3, 31)]
    manifests: dict = {"exchanges": {}}
    prepared_manifest: dict = {"exchanges": {}}
    for name in EXCHANGES:
        (real / f"{name}_hourly.json").write_text(json.dumps(hourly), encoding="utf-8")
        manifests["exchanges"][name] = {
            "exchange": name,
            "data_sha256": source_data_identity(hourly),
        }
        units = {"1d": daily, "1w": weekly, "1mo": monthly}
        frame_info = {}
        for family, rows in units.items():
            (prepped / f"{name}_{family}.json").write_text(json.dumps(rows), encoding="utf-8")
            frame_info[family] = {"data_sha256": source_data_identity(rows)}
        prepared_manifest["exchanges"][name] = {
            "exchange": name,
            "timeframes": frame_info,
        }
    (real / "manifest.json").write_text(json.dumps(manifests), encoding="utf-8")
    (prepped / "prepared_manifest.json").write_text(json.dumps(prepared_manifest), encoding="utf-8")
    return real, prepped


class SourceOnlyE2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.real, self.prepped = fixture(Path(self.tmp.name))
        self.window = validate_window(START, END, APPROVED, now=CLOCK)

    def test_bounded_window_and_required_custody_disclaimer(self):
        self.assertFalse(self.window["independent_dev_boundary_custody_verified"])
        self.assertFalse(self.window["science_or_training_authorized"])
        self.assertEqual(self.window["requested_end_utc"], END)

    def test_short_future_and_overlimit_requests_fail(self):
        cases = [
            (START, "2020-01-02T00:00:00Z", APPROVED),
            (START, "2020-06-01T00:00:00Z", "2020-07-01T00:00:00Z"),
            ("2026-11-15T00:00:00Z", "2026-11-19T00:00:00Z", "2026-11-20T00:00:00Z"),
        ]
        for a, b, c in cases:
            with self.subTest(start=a, end=b):
                with self.assertRaises(ValueError):
                    validate_window(a, b, c, now=CLOCK)

    def test_development_end_not_automatically_authorized(self):
        with self.assertRaises(ValueError):
            validate_window(START, END, "2020-01-03T00:00:00Z", now=CLOCK)
        with self.assertRaises(ValueError):
            validate_window("2012-01-01T00:00:00Z", END, APPROVED, now=CLOCK)

    def test_partial_days_and_non_utc_boundaries_fail(self):
        with self.assertRaises(ValueError):
            validate_window(START, "2020-01-04T01:00:00Z", APPROVED, now=CLOCK)
        with self.assertRaises(ValueError):
            validate_window("2020-01-01T00:00:00-05:00", END, APPROVED, now=CLOCK)

    def test_output_covers_two_venues_and_exact_13_horizons(self):
        r = build_metadata_report(self.real, self.prepped, self.window)
        self.assertEqual(set(r["venues"]), set(EXCHANGES))
        for venue in r["venues"].values():
            self.assertEqual(len(venue["one_origin_per_horizon_at_dev_end"]), 13)
            self.assertEqual(venue["technical_family_coverage"]["1h"]["closed_bucket_count"], 72)
            self.assertEqual(venue["technical_family_coverage"]["1mo"]["closed_bucket_count"], 0)
            self.assertEqual(venue["technical_family_coverage"]["1h"]["source_gap_breaks"], 0)
            self.assertFalse(
                venue["one_origin_per_horizon_at_dev_end"]["4h"]["eligible_technical_origin_at_end"]
            )
        self.assertFalse(r["eligible_for_model_training_or_stage7"])
        self.assertFalse(r["historical_first_seen_independently_verified"])
        for forbidden in ('"open":', '"close":', '"volume":'):
            self.assertNotIn(forbidden, json.dumps(r))

    def test_missing_hour_reported_without_imputation(self):
        path = self.real / "bitstamp_hourly.json"
        rows = json.loads(path.read_text(encoding="utf-8"))
        del rows[30]
        path.write_text(json.dumps(rows), encoding="utf-8")
        manifest = self.real / "manifest.json"
        raw = json.loads(manifest.read_text(encoding="utf-8"))
        raw["exchanges"]["bitstamp"]["data_sha256"] = source_data_identity(rows)
        manifest.write_text(json.dumps(raw), encoding="utf-8")
        cov = build_metadata_report(self.real, self.prepped, self.window)
        hourly = cov["venues"]["bitstamp"]["technical_family_coverage"]["1h"]
        self.assertEqual(hourly["source_gap_breaks"], 1)
        self.assertEqual(hourly["closed_bucket_count"], 71)

    def test_missing_prepared_completeness_flag_rejected(self):
        path = self.prepped / "bitstamp_1d.json"
        rows = json.loads(path.read_text(encoding="utf-8"))
        del rows[0]["is_complete"]
        path.write_text(json.dumps(rows), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "malformed complete flag"):
            build_metadata_report(self.real, self.prepped, self.window)

    def test_tampered_source_digest_fails(self):
        manifest = self.real / "manifest.json"
        raw = json.loads(manifest.read_text(encoding="utf-8"))
        raw["exchanges"]["bitfinex"]["data_sha256"] = "0" * 64
        manifest.write_text(json.dumps(raw), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            build_metadata_report(self.real, self.prepped, self.window)

    def test_out_of_period_source_record_rejected(self):
        path = self.real / "bitstamp_hourly.json"
        rows = json.loads(path.read_text(encoding="utf-8"))
        rows.append(bar(datetime(2020, 1, 4, tzinfo=UTC)))
        path.write_text(json.dumps(rows), encoding="utf-8")
        manifest = self.real / "manifest.json"
        raw = json.loads(manifest.read_text(encoding="utf-8"))
        raw["exchanges"]["bitstamp"]["data_sha256"] = source_data_identity(rows)
        manifest.write_text(json.dumps(raw), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "outside approved interval"):
            build_metadata_report(self.real, self.prepped, self.window)


if __name__ == "__main__":
    unittest.main()
