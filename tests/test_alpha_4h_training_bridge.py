"""Synthetic-only timing tests; no evidence of real BTC predictive skill."""

import math
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from scripts.alpha_4h_training_bridge import (
    FiveMinuteTarget,
    fit_matured_comparisons,
    make_matured_example,
    predict_unscored_four_hour,
    walk_forward_development_diagnostic,
)
from scripts.alpha_interaction_candidate import HourlyClose


class FourHourTrainingBridgeTests(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 9, 1, tzinfo=UTC)
        self.fit_at = self.start + timedelta(days=10)

    def example(self, n=0):
        origin = self.start + timedelta(hours=4 * n)
        bars = []
        for j in range(25):
            opened = origin - timedelta(hours=25 - j)
            price = 50000 * math.exp(
                0.0002 * (4 * n - (25 - j)) + 0.007 * math.sin((4 * n + j) / 7)
            )
            bars.append(HourlyClose(opened, price, opened + timedelta(hours=1, seconds=5)))
        target = FiveMinuteTarget(
            origin + timedelta(hours=4, minutes=10),
            bars[-1].close_usd * math.exp(0.001 * math.cos(n)),
            origin + timedelta(hours=4, minutes=15, seconds=10),
        )
        return origin, origin + timedelta(minutes=10), bars, target

    def build(self, n=0, fit_at=None):
        o, i, b, t = self.example(n)
        return make_matured_example(
            b,
            origin_utc=o,
            issued_at_utc=i,
            target=t,
            fit_at_utc=self.fit_at if fit_at is None else fit_at,
        )

    def test_chronology_connects_to_four_numeric_models(self):
        examples = [self.build(n) for n in range(35)]
        model = fit_matured_comparisons(examples, fit_at_utc=self.fit_at, ridge=100.0)
        self.assertEqual(model.training_rows, 35)
        o, i, bars, _ = self.example(72)
        result = predict_unscored_four_hour(model, bars, origin_utc=o, issued_at_utc=i)
        self.assertAlmostEqual(result.persistence_usd, bars[-1].close_usd)
        self.assertTrue(
            all(
                value > 0
                for value in (result.candidate_usd, result.ablation_usd, result.placebo_usd)
            )
        )

    def test_walk_forward_scores_only_matured_past_outcomes(self):
        rows = [self.build(n) for n in range(36)]
        report = walk_forward_development_diagnostic(rows, ridge=100.0)
        self.assertEqual(report.expected_slots_between_first_and_last, 36)
        self.assertEqual(report.missing_origin_slots, 0)
        self.assertEqual(report.cold_start_rows, 31)
        self.assertEqual(len(report.scored_rows), 5)
        self.assertEqual(report.scored_rows[0].eligible_training_rows, 30)
        self.assertEqual(report.scored_rows[0].origin_utc, self.example(31)[0])
        self.assertAlmostEqual(
            report.scored_rows[0].persistence_abs_log_error,
            abs(rows[31].realized_log_return),
        )
        self.assertIsNotNone(report.mean_candidate_abs_log_error)

    def test_walk_forward_refuses_immature_preceding_label(self):
        rows = [self.build(n) for n in range(36)]
        rows[29] = replace(
            rows[29],
            target_first_observed_at_utc=self.start + timedelta(days=9),
        )
        report = walk_forward_development_diagnostic(rows, ridge=100.0)
        self.assertEqual(report.cold_start_rows, 32)
        self.assertEqual(report.scored_rows[0].origin_utc, self.example(32)[0])
        self.assertEqual(report.scored_rows[0].eligible_training_rows, 30)

    def test_walk_forward_reports_missing_origin_instead_of_hiding_it(self):
        rows = [self.build(n) for n in range(36) if n != 20]
        report = walk_forward_development_diagnostic(rows, ridge=100.0)
        self.assertEqual(report.expected_slots_between_first_and_last, 36)
        self.assertEqual(report.supplied_matured_rows, 35)
        self.assertEqual(report.missing_origin_slots, 1)

    def test_model_fit_after_issue_is_blocked(self):
        examples = [self.build(n) for n in range(30)]
        model = fit_matured_comparisons(examples, fit_at_utc=self.fit_at, ridge=100.0)
        o, i, bars, _ = self.example(36)
        with self.assertRaisesRegex(ValueError, "fitted after prediction issue"):
            predict_unscored_four_hour(model, bars, origin_utc=o, issued_at_utc=i)

    def test_future_label_blocked(self):
        o, i, bars, target = self.example()
        with self.assertRaisesRegex(ValueError, "unmatured"):
            make_matured_example(
                bars,
                origin_utc=o,
                issued_at_utc=i,
                target=target,
                fit_at_utc=o + timedelta(hours=4),
            )

    def test_wrong_target_close_blocked(self):
        o, i, bars, target = self.example()
        with self.assertRaisesRegex(ValueError, "wrong fixed"):
            make_matured_example(
                bars,
                origin_utc=o,
                issued_at_utc=i,
                target=replace(target, bar_open_utc=target.bar_open_utc - timedelta(minutes=5)),
                fit_at_utc=self.fit_at,
            )

    def test_late_issue_blocked(self):
        o, _, bars, target = self.example()
        with self.assertRaisesRegex(ValueError, r"S..S\+15m"):
            make_matured_example(
                bars,
                origin_utc=o,
                issued_at_utc=o + timedelta(minutes=16),
                target=target,
                fit_at_utc=self.fit_at,
            )

    def test_future_feature_blocked(self):
        o, i, bars, target = self.example()
        bars[-1] = replace(bars[-1], first_observed_at_utc=i + timedelta(seconds=1))
        with self.assertRaisesRegex(ValueError, "after issue"):
            make_matured_example(
                bars,
                origin_utc=o,
                issued_at_utc=i,
                target=target,
                fit_at_utc=self.fit_at,
            )

    def test_missing_input_bar_blocked(self):
        o, i, bars, target = self.example()
        with self.assertRaisesRegex(ValueError, "25 bars"):
            make_matured_example(
                bars[:-1],
                origin_utc=o,
                issued_at_utc=i,
                target=target,
                fit_at_utc=self.fit_at,
            )

    def test_mutated_future_label_blocked_at_fit(self):
        examples = [self.build(n) for n in range(30)]
        examples[-1] = replace(
            examples[-1],
            target_first_observed_at_utc=self.fit_at + timedelta(seconds=1),
        )
        with self.assertRaisesRegex(ValueError, "unmatured"):
            fit_matured_comparisons(examples, fit_at_utc=self.fit_at, ridge=100.0)

    def test_duplicate_training_origin_blocked(self):
        examples = [self.build(n) for n in range(30)]
        examples[1] = examples[0]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            fit_matured_comparisons(examples, fit_at_utc=self.fit_at, ridge=100.0)

    def test_naive_clock_and_nonfinite_price_blocked(self):
        o, i, bars, target = self.example()
        with self.assertRaisesRegex(ValueError, "UTC"):
            make_matured_example(
                bars,
                origin_utc=o.replace(tzinfo=None),
                issued_at_utc=i,
                target=target,
                fit_at_utc=self.fit_at,
            )
        with self.assertRaisesRegex(ValueError, "positive finite"):
            make_matured_example(
                bars,
                origin_utc=o,
                issued_at_utc=i,
                target=replace(target, close_usd=float("nan")),
                fit_at_utc=self.fit_at,
            )
