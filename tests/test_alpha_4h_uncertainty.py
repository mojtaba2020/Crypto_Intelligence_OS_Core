"""Synthetic audit tests only. Price forecasts are NOT proven accurate."""

import math
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from scripts.alpha_4h_training_bridge import WalkForwardReport, WalkForwardScore
from scripts.alpha_4h_uncertainty import audit_causal_uncertainty


class CausalUncertaintyTests(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 9, 1, tzinfo=UTC)

    def rows(self, n=39, prediction=0.02, realized=0.016):
        result = []
        for i in range(n):
            origin = self.start + timedelta(hours=4 * i)
            actual = realized * (1 if i % 2 == 0 else 0.9)
            result.append(
                WalkForwardScore(
                    origin_utc=origin,
                    issued_at_utc=origin + timedelta(minutes=10),
                    target_first_observed_at_utc=origin + timedelta(hours=4, minutes=15, seconds=1),
                    reference_close_usd=50000.0,
                    eligible_training_rows=31 + i,
                    candidate_abs_log_error=abs(prediction - actual),
                    ablation_abs_log_error=abs(actual),
                    placebo_abs_log_error=abs(actual),
                    persistence_abs_log_error=abs(actual),
                    interaction_applied=True,
                    realized_log_return=actual,
                    candidate_predicted_log_return=prediction,
                    ablation_predicted_log_return=0.0,
                    placebo_predicted_log_return=0.0,
                )
            )
        return result

    def report(self, rows):
        return WalkForwardReport(
            expected_slots_between_first_and_last=len(rows),
            supplied_matured_rows=len(rows),
            missing_origin_slots=0,
            cold_start_rows=0,
            scored_rows=tuple(rows),
            mean_candidate_abs_log_error=None,
            mean_ablation_abs_log_error=None,
            mean_placebo_abs_log_error=None,
            mean_persistence_abs_log_error=None,
        )

    def test_fixed_calibration_excludes_preceding_unmatured_origin(self):
        rows = self.rows()
        audit = audit_causal_uncertainty(self.report(rows))
        # At origin 32, index 31's target not yet observed at S+10m;
        # index 33 is first with 32 actually observed previous labels.
        self.assertEqual(audit.without_prior_calibration, 33)
        self.assertEqual(audit.calibrated_origins, 6)
        self.assertEqual(audit.up_calls, 6)
        self.assertEqual(audit.down_calls, 0)
        self.assertEqual(audit.correct_calls, 6)
        self.assertEqual(audit.decisions[0].origin_utc, rows[33].origin_utc)
        self.assertTrue(all(row.calibration_rows == 32 for row in audit.decisions))
        self.assertTrue(all(row.lower_price_usd > 0 for row in audit.decisions))

    def test_small_signal_abstains_without_faking_directional_accuracy(self):
        rows = self.rows(prediction=0.0001, realized=0.012)
        audit = audit_causal_uncertainty(self.report(rows))
        self.assertEqual(audit.up_calls + audit.down_calls, 0)
        self.assertEqual(audit.abstentions, 6)
        self.assertIsNone(audit.directional_hit_rate_on_calls_pct)
        self.assertEqual(audit.all_bridge_expected_call_rate_pct, 0.0)

    def test_delayed_label_cannot_calibrate_a_future_issued_origin(self):
        rows = self.rows()
        rows[31] = replace(
            rows[31],
            target_first_observed_at_utc=self.start + timedelta(days=20),
        )
        audit = audit_causal_uncertainty(self.report(rows))
        self.assertEqual(audit.without_prior_calibration, 34)
        self.assertEqual(audit.calibrated_origins, 5)
        self.assertEqual(audit.decisions[0].origin_utc, rows[34].origin_utc)

    def test_modifying_future_outcome_cannot_change_prior_interval(self):
        rows = self.rows()
        first = audit_causal_uncertainty(self.report(rows)).decisions[0]
        row = rows[-1]
        modified = replace(
            row,
            realized_log_return=0.9,
            candidate_abs_log_error=abs(row.candidate_predicted_log_return - 0.9),
        )
        after = audit_causal_uncertainty(self.report([*rows[:-1], modified]))
        self.assertEqual(first, after.decisions[0])

    def test_detects_forged_error_and_duplicate_origin(self):
        rows = self.rows()
        rows[3] = replace(rows[3], candidate_abs_log_error=math.nan)
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            audit_causal_uncertainty(self.report(rows))
        rows = self.rows()
        rows[3] = rows[2]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            audit_causal_uncertainty(self.report(rows))

    def test_future_labeled_row_does_not_claim_90_percent_guarantee(self):
        rows = self.rows()
        audit = audit_causal_uncertainty(self.report(rows))
        self.assertLessEqual(audit.interval_coverage_pct, 100)
        self.assertEqual(audit.total_scored_origins, len(rows))
        self.assertEqual(
            audit.up_calls + audit.down_calls + audit.abstentions,
            audit.calibrated_origins,
        )
