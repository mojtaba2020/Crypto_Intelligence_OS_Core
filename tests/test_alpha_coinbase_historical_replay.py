"""Synthetic-only tests of the offline replay wrapper; no empirical BTC skill."""

import math
import unittest
from datetime import UTC, datetime, timedelta

from scripts.alpha_coinbase_historical_replay import run_replay


class CoinbaseHistoricalReplayTests(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 10, 1, tzinfo=UTC)
        self.end = self.start + timedelta(days=8)
        self.hourly = {}
        cursor = self.start - timedelta(hours=25)
        while cursor < self.end:
            index = int((cursor - self.start) / timedelta(hours=1))
            self.hourly[cursor] = 60000 * math.exp(0.0004 * index + 0.008 * math.sin(index / 13))
            cursor += timedelta(hours=1)
        self.five = {}
        cursor = self.start
        while cursor < self.end:
            target_open = cursor + timedelta(hours=4, minutes=10)
            self.five[target_open] = self.hourly[cursor - timedelta(hours=1)] * math.exp(
                0.003 * math.sin(int((cursor - self.start) / timedelta(hours=4)))
            )
            cursor += timedelta(hours=4)

    def test_realistic_timed_replay_produces_causal_4way_comparison(self):
        report = run_replay(self.hourly, self.five, start=self.start, end=self.end)
        self.assertEqual(report["scheduled_slots"], 48)
        self.assertEqual(report["complete_historical_rows"], 48)
        self.assertEqual(report["cold_start_rows"], 31)
        self.assertEqual(report["scored_historical_origins"], 17)
        self.assertIsNotNone(report["mean_absolute_log_price_error"]["candidate"])
        self.assertIsNotNone(report["direction_secondary_nonflat"]["candidate"])
        self.assertFalse(report["data_first_observed_authenticated"])
        self.assertEqual(report["model_status"], "NO_RUN_NO_FREEZE_FOR_SCIENTIFIC_CONFIRMATION")

    def test_missing_5min_target_stays_missing(self):
        self.five.pop(self.start + timedelta(hours=4, minutes=10))
        report = run_replay(self.hourly, self.five, start=self.start, end=self.end)
        self.assertEqual(report["scheduled_slots"], 48)
        self.assertEqual(report["complete_historical_rows"], 47)
        self.assertEqual(report["rejected_origins"]["missing_5m"], 1)

    def test_missing_hourly_data_not_imputed(self):
        self.hourly.pop(self.start - timedelta(hours=1))
        report = run_replay(self.hourly, self.five, start=self.start, end=self.end)
        self.assertGreater(report["rejected_origins"]["missing_1h"], 0)
        self.assertLess(report["complete_historical_rows"], 48)

    def test_one_day_window_is_refused(self):
        with self.assertRaisesRegex(ValueError, "complete UTC days"):
            run_replay(
                self.hourly,
                self.five,
                start=self.start,
                end=self.start + timedelta(days=1),
            )
