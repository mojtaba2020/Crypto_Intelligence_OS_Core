"""Synthetic-only tests; these do NOT validate BTC forecasting skill."""

import math
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from scripts.alpha_4h_training_bridge import FiveMinuteTarget
from scripts.alpha_volume_confirmation import (
    HourlyVolumeBar,
    make_volume_training_row,
    volume_confirmation_features,
    walk_forward_volume_candidate,
)


class VolumeConfirmationTests(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 10, 1, tzinfo=UTC)
        self.fit_at = self.start + timedelta(days=20)

    def raw(self, n=0, *, constant_volume=False):
        origin = self.start + timedelta(hours=4 * n)
        bars = []
        for j in range(25):
            open_at = origin - timedelta(hours=25 - j)
            close = 60000 * math.exp(
                0.0003 * (4 * n - 25 + j) + 0.006 * math.sin((4 * n + j) / 10)
            )
            volume = 10.0 if constant_volume else 8.0 + 2.5 * (
                1.0 + math.sin((4 * n + j) / 9)
            )
            bars.append(
                HourlyVolumeBar(
                    bar_open_utc=open_at,
                    close_usd=close,
                    base_volume_btc=volume,
                    first_observed_at_utc=open_at + timedelta(hours=1, seconds=5),
                )
            )
        target = FiveMinuteTarget(
            bar_open_utc=origin + timedelta(hours=4, minutes=10),
            close_usd=bars[-1].close_usd * math.exp(0.002 * math.cos(n / 3)),
            first_observed_at_utc=origin + timedelta(hours=4, minutes=15, seconds=5),
        )
        return origin, origin + timedelta(minutes=10), bars, target

    def record(self, n=0, *, constant_volume=False):
        origin, issue, bars, target = self.raw(n, constant_volume=constant_volume)
        return make_volume_training_row(
            bars,
            origin_utc=origin,
            issued_at_utc=issue,
            target=target,
            fit_at_utc=self.fit_at,
        )

    def test_volume_surprise_constant_volume_is_zero(self):
        _, issue, bars, _ = self.raw(constant_volume=True)
        m, v, interaction = volume_confirmation_features(bars, issued_at_utc=issue)
        self.assertAlmostEqual(v, 0.0, places=13)
        self.assertAlmostEqual(interaction, m * v, places=13)

    def test_volume_signal_changes_when_recent_completed_volume_rises(self):
        _, issue, bars, _ = self.raw(constant_volume=True)
        baseline = volume_confirmation_features(bars, issued_at_utc=issue)
        for j in range(21, 25):
            bars[j] = replace(bars[j], base_volume_btc=20.0)
        m, v, product = volume_confirmation_features(bars, issued_at_utc=issue)
        self.assertAlmostEqual(m, baseline[0])
        self.assertAlmostEqual(v, math.log(2.0))
        self.assertAlmostEqual(product, m * v)

    def test_rejects_volume_observed_after_forecast(self):
        origin, issue, bars, target = self.raw()
        bars[-1] = replace(bars[-1], first_observed_at_utc=issue + timedelta(seconds=1))
        with self.assertRaisesRegex(ValueError, "available"):
            make_volume_training_row(
                bars, origin_utc=origin, issued_at_utc=issue,
                target=target, fit_at_utc=self.fit_at,
            )

    def test_rejects_zero_volume_and_holes(self):
        _, issue, bars, _ = self.raw()
        bars[-3] = replace(bars[-3], base_volume_btc=0.0)
        with self.assertRaisesRegex(ValueError, "positive"):
            volume_confirmation_features(bars, issued_at_utc=issue)
        _, issue, bars, _ = self.raw()
        bars[12] = replace(bars[12], bar_open_utc=bars[12].bar_open_utc + timedelta(minutes=5))
        with self.assertRaisesRegex(ValueError, "nonconsecutive"):
            volume_confirmation_features(bars, issued_at_utc=issue)

    def test_rejects_unmature_target_and_wrong_five_minute_interval(self):
        origin, issue, bars, target = self.raw()
        with self.assertRaisesRegex(ValueError, "unmatured"):
            make_volume_training_row(
                bars, origin_utc=origin, issued_at_utc=issue, target=target,
                fit_at_utc=origin + timedelta(hours=4),
            )
        with self.assertRaisesRegex(ValueError, "wrong fixed"):
            make_volume_training_row(
                bars, origin_utc=origin, issued_at_utc=issue,
                target=replace(target, bar_open_utc=target.bar_open_utc + timedelta(minutes=5)),
                fit_at_utc=self.fit_at,
            )

    def test_walk_forward_matured_only_and_comparable_baselines(self):
        examples = [self.record(n) for n in range(45)]
        audit = walk_forward_volume_candidate(examples, ridge=100.0)
        self.assertEqual(audit.supplied_origins, 45)
        self.assertEqual(audit.cold_start_origins, 31)
        self.assertEqual(len(audit.scored), 14)
        self.assertEqual(audit.scored[0].eligible_training_rows, 30)
        self.assertEqual(audit.scored[0].origin_utc, self.raw(31)[0])
        self.assertAlmostEqual(
            audit.scored[0].persistence_abs_log_error,
            abs(audit.scored[0].realized_log_return),
        )

    def test_delayed_prior_label_never_added_to_training(self):
        rows = [self.record(n) for n in range(40)]
        rows[29] = replace(
            rows[29], target_first_observed_at_utc=self.start + timedelta(days=19)
        )
        audit = walk_forward_volume_candidate(rows)
        self.assertEqual(audit.scored[0].origin_utc, self.raw(32)[0])
        self.assertEqual(audit.scored[0].eligible_training_rows, 30)

    def test_constant_volume_interaction_cannot_fake_gain(self):
        rows = [self.record(n, constant_volume=True) for n in range(40)]
        audit = walk_forward_volume_candidate(rows)
        self.assertTrue(audit.scored)
        for scored in audit.scored:
            self.assertFalse(scored.interaction_active)
            self.assertAlmostEqual(scored.candidate_log_return, scored.additive_log_return)
            self.assertAlmostEqual(scored.candidate_log_return, scored.momentum_log_return)

    def test_missing_origin_reported_not_backfilled(self):
        rows = [self.record(n) for n in range(45) if n != 19]
        audit = walk_forward_volume_candidate(rows)
        self.assertEqual(audit.expected_origins_between_bounds, 45)
        self.assertEqual(audit.missing_origin_slots, 1)
