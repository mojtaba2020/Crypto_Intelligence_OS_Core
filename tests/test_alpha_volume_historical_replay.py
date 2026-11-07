"""Tests for the bounded historical replay; these use invented candles only."""

import math
import unittest
from datetime import UTC, datetime, timedelta

from scripts.alpha_volume_historical_replay import run_volume_historical_replay


class VolumeResearchReplayTests(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 10, 1, tzinfo=UTC)
        self.end = self.start + timedelta(days=8)
        self.hourly = {}
        t = self.start - timedelta(hours=25)
        while t < self.end:
            n = int((t - self.start) / timedelta(hours=1))
            close = 50000 * math.exp(0.0003 * n + 0.01 * math.sin(n / 13))
            volume = 12.0 + 3.5 * (1.0 + math.sin(n / 9))
            self.hourly[t] = (close, volume)
            t += timedelta(hours=1)
        self.targets = {}
        t = self.start
        while t < self.end:
            n = int((t - self.start) / timedelta(hours=4))
            future = t + timedelta(hours=4, minutes=10)
            self.targets[future] = self.hourly[t - timedelta(hours=1)][0] * math.exp(
                0.002 * math.cos(n)
            )
            t += timedelta(hours=4)

    def test_bounded_historical_diagnostic_has_valid_baselines(self):
        result = run_volume_historical_replay(
            self.hourly, self.targets, start=self.start, end=self.end
        )
        self.assertEqual(result["scheduled_origins"], 48)
        self.assertEqual(result["complete_origins"], 48)
        self.assertEqual(result["cold_start_origins"], 31)
        self.assertEqual(result["walk_forward_scored"], 17)
        self.assertTrue(
            all(
                math.isfinite(value)
                for value in result["mean_absolute_log_price_error"].values()
            )
        )
        self.assertFalse(result["initial_source_vintage_proven"])
        self.assertFalse(result["original_forecasts_issued_on_these_dates"])
        self.assertEqual(result["research_status"], "NO_RUN_NO_FREEZE_NO_TRADE")

    def test_missing_hourly_volume_is_reported_not_filled(self):
        self.hourly.pop(self.start - timedelta(hours=1))
        report = run_volume_historical_replay(
            self.hourly, self.targets, start=self.start, end=self.end
        )
        self.assertGreater(report["rejected_origin_reasons"]["missing_1h_ohlcv"], 0)
        self.assertLess(report["complete_origins"], report["scheduled_origins"])

    def test_missing_target_remains_missing(self):
        self.targets.pop(self.start + timedelta(hours=4, minutes=10))
        report = run_volume_historical_replay(
            self.hourly, self.targets, start=self.start, end=self.end
        )
        self.assertEqual(report["rejected_origin_reasons"]["missing_5min_target"], 1)
        self.assertEqual(report["missing_origins"], 1)

    def test_less_than_seven_days_is_refused(self):
        with self.assertRaisesRegex(ValueError, "7..38"):
            run_volume_historical_replay(
                self.hourly,
                self.targets,
                start=self.start,
                end=self.start + timedelta(days=1),
            )
