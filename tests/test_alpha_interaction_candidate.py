"""Synthetic unit tests only: these do not validate BTC predictive accuracy."""

import math
import unittest
from datetime import UTC, datetime, timedelta

from scripts.alpha_interaction_candidate import (
    HourlyClose,
    fit_candidate_and_ablation,
    interaction_features,
    predict_log_returns,
)


class AlphaInteractionCandidateTests(unittest.TestCase):
    def setUp(self):
        self.issue = datetime(2026, 10, 24, 12, 15, tzinfo=UTC)
        self.bars = []
        for i in range(25):
            opened = self.issue - timedelta(hours=25 - i, minutes=15)
            self.bars.append(
                HourlyClose(
                    bar_open_utc=opened,
                    close_usd=100.0 * math.exp(0.002 * i),
                    first_observed_at_utc=opened + timedelta(hours=1, seconds=10),
                )
            )

    def test_past_only_momentum_features(self):
        m, v, interaction = interaction_features(self.bars, issue_at_utc=self.issue)
        self.assertAlmostEqual(m, 0.048)
        self.assertAlmostEqual(v, 0.0, places=12)
        self.assertAlmostEqual(interaction, m * v)

    def test_nonzero_volatility_and_interaction(self):
        varied = [
            HourlyClose(
                bar.bar_open_utc,
                bar.close_usd * (1.03 if i % 2 else 1.0),
                bar.first_observed_at_utc,
            )
            for i, bar in enumerate(self.bars)
        ]
        m, v, interaction = interaction_features(varied, issue_at_utc=self.issue)
        self.assertGreater(v, 0)
        self.assertAlmostEqual(interaction, m * v)

    def test_future_feature_arrival_refused(self):
        self.bars[-1] = HourlyClose(
            self.bars[-1].bar_open_utc,
            self.bars[-1].close_usd,
            self.issue + timedelta(seconds=1),
        )
        with self.assertRaisesRegex(ValueError, "after issue"):
            interaction_features(self.bars, issue_at_utc=self.issue)

    def test_feature_arrival_before_bar_end_refused(self):
        self.bars[-1] = HourlyClose(
            self.bars[-1].bar_open_utc,
            self.bars[-1].close_usd,
            self.bars[-1].bar_open_utc + timedelta(minutes=59),
        )
        with self.assertRaisesRegex(ValueError, "before hour completed"):
            interaction_features(self.bars, issue_at_utc=self.issue)

    def test_missing_hour_refused_without_interpolation(self):
        self.bars[12] = HourlyClose(
            self.bars[12].bar_open_utc + timedelta(minutes=10),
            self.bars[12].close_usd,
            self.bars[12].first_observed_at_utc,
        )
        with self.assertRaisesRegex(ValueError, "Nonconsecutive"):
            interaction_features(self.bars, issue_at_utc=self.issue)

    def test_invalid_price_or_wrong_count_refused(self):
        with self.assertRaisesRegex(ValueError, "Exactly 25"):
            interaction_features(self.bars[:-1], issue_at_utc=self.issue)
        self.bars[0] = HourlyClose(
            self.bars[0].bar_open_utc, float("nan"), self.bars[0].first_observed_at_utc
        )
        with self.assertRaisesRegex(ValueError, "Invalid positive"):
            interaction_features(self.bars, issue_at_utc=self.issue)

    def test_fit_nested_pair_same_training_rows(self):
        rows = []
        for i in range(80):
            m = ((i % 17) - 8) * 0.013
            v = 0.002 + (i % 11) * 0.002
            interaction = m * v
            # Invented labels test software, not actual BTC forecasting skill.
            y = 0.3 * m + 14.0 * interaction
            rows.append(((m, v, interaction), y))
        pair = fit_candidate_and_ablation(rows, ridge=1.0)
        self.assertEqual(pair.training_rows, 80)
        self.assertEqual(len(pair.candidate_fit[0]), 4)
        self.assertEqual(len(pair.ablation_fit[0]), 3)
        result = predict_log_returns(pair, (0.04, 0.01, 0.0004))
        self.assertEqual(len(result), 3)
        self.assertTrue(all(math.isfinite(v) for v in result))
        self.assertEqual(result[-1], 0)
        self.assertNotAlmostEqual(result[0], result[1], places=9)

    def test_bad_training_rows_fail_closed(self):
        example = ((0.02, 0.004, 0.00008), 0.0003)
        with self.assertRaisesRegex(ValueError, "At least 30"):
            fit_candidate_and_ablation([example] * 29, ridge=1.0)
        with self.assertRaisesRegex(ValueError, "strictly positive"):
            fit_candidate_and_ablation([example] * 30, ridge=0)
        malformed = ((0.02, 0.004, 0.002), 0.001)
        with self.assertRaisesRegex(ValueError, "Malformed"):
            fit_candidate_and_ablation([malformed] * 30, ridge=1.0)

    def test_invalid_features_are_not_predictions(self):
        rows = [((0.02, 0.004, 0.00008), 0.0003)] * 30
        pair = fit_candidate_and_ablation(rows, ridge=1.0)
        with self.assertRaisesRegex(ValueError, "Invalid interaction"):
            predict_log_returns(pair, (0.02, 0.004, 0.5))
        with self.assertRaisesRegex(ValueError, "Invalid feature"):
            predict_log_returns(pair, (math.nan, 0.004, 0.0))


if __name__ == "__main__":
    unittest.main()
