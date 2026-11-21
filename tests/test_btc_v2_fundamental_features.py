"""Synthetic-only time-vintage and fusion safety checks for BTC V2."""

from __future__ import annotations

import unittest

from scripts.btc_v2_fundamental_features import (
    METRICS,
    merge_research_features,
    summarize_fundamentals,
    validate_observation,
)
from scripts.btc_v2_news_evidence import EvidenceError
from scripts.btc_v2_news_features import summarize_news

CUTOFF = "2026-11-16T19:10:00Z"


def entry(**overrides):
    item = {
        "metric_id": "btc_spot_etf_net_flow_usd",
        "value": 125000000.0,
        "unit": "USD",
        "source": "fixture-only",
        "source_url": "https://example.org/etf-data",
        "observation_end_utc": "2026-11-13T21:00:00Z",
        "published_at_utc": "2026-11-14T01:00:00Z",
        "first_seen_at_utc": "2026-11-14T01:05:00Z",
        "fetched_at_utc": "2026-11-14T01:07:00Z",
        "revision_id": "v1",
    }
    item.update(overrides)
    return item


class FundamentalFeatureTests(unittest.TestCase):
    def test_registered_families_and_null_missing_not_fake_zero(self):
        summary = summarize_fundamentals([entry()], CUTOFF)
        self.assertEqual(summary["available_metric_count"], 1)
        self.assertEqual(summary["values"]["btc_spot_etf_net_flow_usd"], 125000000.0)
        self.assertIsNone(summary["values"]["macro_cpi_surprise"])
        self.assertFalse(summary["has_value"]["macro_cpi_surprise"])
        self.assertFalse(summary["train_eligible"])
        self.assertEqual(len(summary["values"]), len(METRICS))

    def test_late_publication_is_excluded_not_backfilled(self):
        late = entry(
            published_at_utc="2026-11-16T19:11:00Z",
            first_seen_at_utc="2026-11-16T19:12:00Z",
            fetched_at_utc="2026-11-16T19:13:00Z",
        )
        s = summarize_fundamentals([late], CUTOFF)
        self.assertEqual(s["excluded_late"], 1)
        self.assertIsNone(s["values"]["btc_spot_etf_net_flow_usd"])

    def test_already_revised_value_cannot_be_used_before_revision(self):
        revised = entry(
            value=999.0,
            first_seen_at_utc="2026-11-17T09:00:00Z",
            fetched_at_utc="2026-11-17T09:01:00Z",
            revised_at_utc="2026-11-17T08:55:00Z",
            revision_id="v2",
        )
        s = summarize_fundamentals([entry(), revised], CUTOFF)
        self.assertEqual(s["values"]["btc_spot_etf_net_flow_usd"], 125000000.0)
        self.assertEqual(s["excluded_late"], 1)

    def test_later_observed_revision_can_replace_old_value(self):
        revised = entry(
            value=90000000.0,
            first_seen_at_utc="2026-11-15T09:00:00Z",
            fetched_at_utc="2026-11-15T09:01:00Z",
            revised_at_utc="2026-11-15T08:55:00Z",
            revision_id="v2",
        )
        summary = summarize_fundamentals([entry(), revised], CUTOFF)
        self.assertEqual(summary["values"]["btc_spot_etf_net_flow_usd"], 90000000.0)
        self.assertEqual(summary["provenance"]["btc_spot_etf_net_flow_usd"]["revision_id"], "v2")

    def test_reject_backdated_and_reversed_publication_order(self):
        with self.assertRaises(EvidenceError):
            validate_observation(entry(first_seen_at_utc="2026-11-12T01:00:00Z"))
        with self.assertRaises(EvidenceError):
            validate_observation(entry(observation_end_utc="2026-11-15T10:00:00Z"))

    def test_reject_future_revision_stamp_vs_first_seen(self):
        with self.assertRaisesRegex(EvidenceError, "revision"):
            validate_observation(entry(revised_at_utc="2026-11-15T01:00:00Z"))

    def test_reject_bad_source_and_metric(self):
        with self.assertRaises(EvidenceError):
            validate_observation(entry(metric_id="unknown_leading_target"))
        with self.assertRaises(EvidenceError):
            validate_observation(entry(source_url="http://example.org"))
        with self.assertRaises(EvidenceError):
            validate_observation(entry(source_url="https://evil@example.org"))

    def test_reject_duplicate_metric_version(self):
        with self.assertRaisesRegex(EvidenceError, "duplicate"):
            summarize_fundamentals([entry(), entry()], CUTOFF)

    def test_reject_bad_numeric_values(self):
        for value in (float("nan"), float("inf"), True, 1e19):
            with self.subTest(value=value):
                with self.assertRaises(EvidenceError):
                    validate_observation(entry(value=value))

    def test_reject_different_source_same_metric(self):
        with self.assertRaisesRegex(EvidenceError, "conflicting"):
            summarize_fundamentals(
                [entry(), entry(source="other-source", revision_id="v2")], CUTOFF
            )

    def test_stale_is_missing_not_zero(self):
        old = entry(
            observation_end_utc="2026-02-01T00:00:00Z",
            published_at_utc="2026-02-02T00:00:00Z",
            first_seen_at_utc="2026-02-02T00:01:00Z",
            fetched_at_utc="2026-02-02T00:02:00Z",
        )
        s = summarize_fundamentals([old], CUTOFF)
        self.assertEqual(s["excluded_stale"], 1)
        self.assertIsNone(s["values"]["btc_spot_etf_net_flow_usd"])

    def test_merge_requires_same_prediction_cutoff(self):
        fund = summarize_fundamentals([], CUTOFF)
        news = summarize_news([], "2026-11-16T19:11:00Z")
        with self.assertRaisesRegex(EvidenceError, "identical"):
            merge_research_features({"momentum": 0.1}, news, fund)

    def test_merge_combines_three_views_but_never_authorizes_training(self):
        fund = summarize_fundamentals([entry()], CUTOFF)
        news = summarize_news([], CUTOFF)
        fused = merge_research_features({"momentum": 0.02, "volume_surprise": 0.3}, news, fund)
        self.assertEqual(fused["technical"]["momentum"], 0.02)
        self.assertEqual(fused["fundamental"]["btc_spot_etf_net_flow_usd"], 125000000.0)
        self.assertTrue(fused["fundamental_missing"]["macro_cpi_surprise"])
        self.assertFalse(fused["train_eligible"])
        self.assertEqual(fused["news"]["count"], 0)


if __name__ == "__main__":
    unittest.main()
