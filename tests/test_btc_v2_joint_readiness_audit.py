"""Synthetic, label-blind 13-horizon readiness checks for BTC research."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from scripts.btc_v2_joint_readiness_audit import (
    HORIZONS,
    MIN_BARS,
    audit_joint_readiness,
)
from scripts.btc_v2_news_evidence import EvidenceError

CUTOFF = "2026-11-20T12:15:00Z"


def as_z(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def monthly_closes(n: int) -> list[dict]:
    return [
        {
            "close_at_utc": as_z(datetime(y, m, 1, tzinfo=UTC)),
            "is_complete": True,
        }
        for y in range(2016, 2027)
        for m in range(1, 13)
        if (y, m) <= (2026, 11)
    ][-n:]


def buckets():
    hourly = datetime(2026, 11, 20, 12, tzinfo=UTC)
    daily = datetime(2026, 11, 20, tzinfo=UTC)
    weekly = datetime(2026, 11, 16, tzinfo=UTC)
    return {
        "1h": [
            {"close_at_utc": as_z(hourly - timedelta(hours=i)), "is_complete": True}
            for i in reversed(range(MIN_BARS["1h"]))
        ],
        "1d": [
            {"close_at_utc": as_z(daily - timedelta(days=i)), "is_complete": True}
            for i in reversed(range(MIN_BARS["1d"]))
        ],
        "1w": [
            {"close_at_utc": as_z(weekly - timedelta(weeks=i)), "is_complete": True}
            for i in reversed(range(MIN_BARS["1w"]))
        ],
        "1mo": monthly_closes(MIN_BARS["1mo"]),
    }


def event(**changes):
    item = {
        "metric_id": "btc_spot_etf_net_flow_usd",
        "value": 100.0,
        "unit": "USD",
        "source": "synthetic",
        "source_url": "https://example.org/etf",
        "observation_end_utc": "2026-11-13T20:00:00Z",
        "published_at_utc": "2026-11-14T01:00:00Z",
        "first_seen_at_utc": "2026-11-14T01:01:00Z",
        "fetched_at_utc": "2026-11-14T01:02:00Z",
        "revision_id": "v1",
    }
    item.update(changes)
    return item


def payload():
    return {
        "origins": [{"horizon": h, "cutoff_utc": CUTOFF} for h in sorted(HORIZONS)],
        "observations": [event()],
        "technical_buckets": buckets(),
    }


class JointReadinessTests(unittest.TestCase):
    def test_all_13_horizons_match_technical_and_fundamental(self):
        result = audit_joint_readiness(payload())
        self.assertEqual(len(result["by_horizon"]), 13)
        for row in result["by_horizon"].values():
            self.assertEqual(row["technical_history_count_ready"], 1)
            self.assertEqual(row["fundamental_any_count"], 1)
            self.assertEqual(row["matched_technical_and_any_fundamental_count"], 1)
        self.assertFalse(result["eligible_for_training_or_promotion"])
        self.assertFalse(result["locked_outcomes_or_future_labels_used"])
        self.assertFalse(result["first_seen_source_independently_attested"])

    def test_missing_one_recent_hour_does_not_invalidate_daily_family(self):
        data = payload()
        del data["technical_buckets"]["1h"][-10]
        result = audit_joint_readiness(data)["by_horizon"]
        self.assertEqual(result["4h"]["technical_short_or_gapped_history_count"], 1)
        self.assertEqual(result["4h"]["matched_technical_and_any_fundamental_count"], 0)
        self.assertEqual(result["1d"]["matched_technical_and_any_fundamental_count"], 1)

    def test_very_old_missing_bars_do_not_poison_recent_window(self):
        data = payload()
        old = datetime(2011, 1, 1, 1, tzinfo=UTC)
        data["technical_buckets"]["1h"].insert(
            0, {"close_at_utc": as_z(old), "is_complete": True}
        )
        self.assertEqual(
            audit_joint_readiness(data)["by_horizon"]["4h"]["technical_history_count_ready"],
            1,
        )

    def test_stale_latest_hour_counts_as_missing(self):
        data = payload()
        del data["technical_buckets"]["1h"][-3:]
        r = audit_joint_readiness(data)["by_horizon"]["4h"]
        self.assertEqual(r["technical_stale_or_unavailable_count"], 1)
        self.assertEqual(r["technical_history_count_ready"], 0)

    def test_future_fundamental_not_available_to_issue(self):
        data = payload()
        data["observations"] = [
            event(
                observation_end_utc="2026-11-20T13:00:00Z",
                published_at_utc="2026-11-20T13:05:00Z",
                first_seen_at_utc="2026-11-20T13:06:00Z",
                fetched_at_utc="2026-11-20T13:07:00Z",
            )
        ]
        r = audit_joint_readiness(data)["by_horizon"]["4h"]
        self.assertEqual(r["technical_history_count_ready"], 1)
        self.assertEqual(r["fundamental_any_count"], 0)
        self.assertEqual(r["matched_technical_and_any_fundamental_count"], 0)

    def test_explicit_incomplete_recent_bucket_breaks_history(self):
        data = payload()
        data["technical_buckets"]["1mo"][-1]["is_complete"] = False
        r = audit_joint_readiness(data)["by_horizon"]
        self.assertEqual(r["1mo"]["technical_history_count_ready"], 0)
        self.assertEqual(r["1d"]["technical_history_count_ready"], 1)

    def test_no_technical_bars_cannot_claim_ready(self):
        data = payload()
        data["technical_buckets"] = {family: [] for family in MIN_BARS}
        self.assertEqual(
            audit_joint_readiness(data)["by_horizon"]["1d"][
                "technical_stale_or_unavailable_count"
            ],
            1,
        )

    def test_reject_future_target_labels_and_extra_fields(self):
        data = payload()
        data["future_target_price"] = 100000
        with self.assertRaises(EvidenceError):
            audit_joint_readiness(data)
        data = payload()
        data["technical_buckets"]["1d"][-1]["close"] = 100000
        with self.assertRaises(EvidenceError):
            audit_joint_readiness(data)

    def test_reject_unordered_duplicate_or_noncanonical_buckets(self):
        for bad in (
            {"close_at_utc": CUTOFF, "is_complete": True},
            {"close_at_utc": "2026-11-20T12:00:00Z", "is_complete": True},
            {"close_at_utc": "2026-11-20T00:00:00Z", "is_complete": 1},
        ):
            with self.subTest(bad=bad):
                data = payload()
                data["technical_buckets"]["1d"].append(bad)
                with self.assertRaises(EvidenceError):
                    audit_joint_readiness(data)

    def test_weekly_wrong_anchor_is_rejected(self):
        data = payload()
        data["technical_buckets"]["1w"][-1]["close_at_utc"] = "2026-11-17T00:00:00Z"
        with self.assertRaises(EvidenceError):
            audit_joint_readiness(data)

    def test_bad_month_and_increasing_clock(self):
        data = payload()
        data["technical_buckets"]["1mo"][-1]["close_at_utc"] = "2026-11-02T00:00:00Z"
        with self.assertRaises(EvidenceError):
            audit_joint_readiness(data)


if __name__ == "__main__":
    unittest.main()
