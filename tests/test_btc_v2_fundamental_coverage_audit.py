"""Synthetic-only, label-blind Stage-6 fundamentals availability audit tests."""

from __future__ import annotations

import unittest

from scripts.btc_v2_fundamental_coverage_audit import HORIZONS, audit_coverage
from scripts.btc_v2_news_evidence import EvidenceError


def observed(**changes):
    value = {
        "metric_id": "btc_spot_etf_net_flow_usd",
        "value": 100.0,
        "unit": "USD",
        "source": "synthetic",
        "source_url": "https://example.org/data",
        "observation_end_utc": "2026-11-13T20:00:00Z",
        "published_at_utc": "2026-11-14T01:00:00Z",
        "first_seen_at_utc": "2026-11-14T01:01:00Z",
        "fetched_at_utc": "2026-11-14T01:02:00Z",
        "revision_id": "v1",
    }
    value.update(changes)
    return value


def origin(horizon="4h", cutoff="2026-11-16T19:10:00Z"):
    return {"horizon": horizon, "cutoff_utc": cutoff}


class CoverageTests(unittest.TestCase):
    def test_all_13_contract_horizons_included(self):
        self.assertEqual(len(HORIZONS), 13)
        result = audit_coverage({"origins": [origin()], "observations": [observed()]})
        self.assertEqual(set(result["horizons"]), HORIZONS)
        row = result["horizons"]["4h"]
        self.assertEqual(row["scheduled_origins"], 1)
        self.assertEqual(row["origins_with_any_metric"], 1)
        self.assertEqual(row["group_any_coverage_counts"]["etf"], 1)
        self.assertEqual(row["metric_coverage_counts"]["macro_cpi_surprise"], 0)
        self.assertFalse(result["training_or_freeze_authorized"])
        self.assertFalse(result["source_first_seen_independently_verified"])
        self.assertFalse(result["labels_or_future_outcomes_used"])

    def test_each_horizon_is_counted_independently(self):
        result = audit_coverage(
            {"origins": [origin("4h"), origin("1d")], "observations": [observed()]}
        )
        self.assertEqual(result["horizons"]["4h"]["covered_origin_fraction"], 1.0)
        self.assertEqual(result["horizons"]["1d"]["covered_origin_fraction"], 1.0)
        self.assertIsNone(result["horizons"]["2w"]["covered_origin_fraction"])

    def test_future_released_data_cannot_cover_earlier_origin(self):
        late = observed(
            published_at_utc="2026-11-16T19:11:00Z",
            first_seen_at_utc="2026-11-16T19:12:00Z",
            fetched_at_utc="2026-11-16T19:13:00Z",
        )
        report = audit_coverage({"origins": [origin()], "observations": [late]})
        row = report["horizons"]["4h"]
        self.assertEqual(row["origins_with_any_metric"], 0)
        self.assertEqual(row["late_observations_excluded"], 1)

    def test_stale_data_remains_missing(self):
        old = observed(
            observation_end_utc="2026-01-01T00:00:00Z",
            published_at_utc="2026-01-02T00:00:00Z",
            first_seen_at_utc="2026-01-02T00:01:00Z",
            fetched_at_utc="2026-01-02T00:02:00Z",
        )
        report = audit_coverage({"origins": [origin()], "observations": [old]})
        self.assertEqual(report["horizons"]["4h"]["stale_observations_excluded"], 1)

    def test_no_observations_is_honest_zero_coverage(self):
        report = audit_coverage({"origins": [origin("1h")], "observations": []})
        self.assertEqual(report["horizons"]["1h"]["covered_origin_fraction"], 0)
        self.assertFalse(report["power_or_predictive_edge_established"])

    def test_reject_unknown_fields_that_could_carry_future_labels(self):
        for data in (
            {"origins": [origin()], "observations": [], "future_prices": [123]},
            {"origins": [dict(origin(), actual_price=12)], "observations": []},
        ):
            with self.subTest(data=data):
                with self.assertRaises(EvidenceError):
                    audit_coverage(data)

    def test_reject_duplicate_or_nonincreasing_origins(self):
        repeated = [origin(), origin()]
        with self.assertRaises(EvidenceError):
            audit_coverage({"origins": repeated, "observations": []})
        backwards = [
            origin("1h", "2026-11-16T20:00:00Z"),
            origin("1d", "2026-11-16T23:00:00Z"),
            origin("1h", "2026-11-16T19:00:00Z"),
        ]
        with self.assertRaisesRegex(EvidenceError, "increase"):
            audit_coverage({"origins": backwards, "observations": []})

    def test_reject_unknown_horizon_and_bad_timestamp(self):
        with self.assertRaises(EvidenceError):
            audit_coverage({"origins": [origin("99h")], "observations": []})
        with self.assertRaises(EvidenceError):
            audit_coverage({"origins": [origin("4h", "bad-time")], "observations": []})

    def test_reject_unbounded_input(self):
        with self.assertRaises(EvidenceError):
            audit_coverage({"origins": [origin()] * 501, "observations": []})

    def test_reject_bad_metadata_even_without_value_usage(self):
        with self.assertRaises(EvidenceError):
            audit_coverage({"origins": [origin()], "observations": [observed(value=float("nan"))]})


if __name__ == "__main__":
    unittest.main()
