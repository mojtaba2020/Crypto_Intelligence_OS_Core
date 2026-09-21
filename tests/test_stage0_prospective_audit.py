"""Offline tests for prospective scoring audit."""

import unittest
from datetime import UTC, datetime, timedelta

from scripts.stage0_prospective_audit import audit


class ProspectiveAuditTests(unittest.TestCase):
    def setUp(self):
        origin = datetime(2026, 1, 1, tzinfo=UTC)
        self.forecast = {
            "version": "test",
            "origin_hour_utc": origin.isoformat(),
            "horizon_hours": 1,
            "issued_at_utc": (origin + timedelta(minutes=5)).isoformat(),
            "target_close_utc": (origin + timedelta(hours=2)).isoformat(),
            "target_hour_utc": (origin + timedelta(hours=1)).isoformat(),
            "forecast_usd": 101.0,
            "persistence_usd": 100.0,
        }
        self.score = {
            "version": "test",
            "origin_hour_utc": origin.isoformat(),
            "horizon_hours": 1,
            "scored_at_utc": (origin + timedelta(hours=2)).isoformat(),
            "actual_close_usd": 102.0,
            "model_absolute_error_usd": 1.0,
            "persistence_absolute_error_usd": 2.0,
        }

    def test_recomputes_scores(self):
        result = audit([self.forecast], [self.score], min_resolved=2)
        self.assertEqual(result["results"][0]["improvement_pct"], 50.0)
        self.assertFalse(result["results"][0]["sample_threshold_met"])
        self.assertEqual(result["results"][0]["forecasts_different_from_persistence"], 1)
        self.assertTrue(result["results"][0]["model_differentiation_observed"])

    def test_identical_model_and_persistence_is_disclosed(self):
        forecast = dict(self.forecast, forecast_usd=100.0)
        score = dict(self.score, model_absolute_error_usd=2.0)
        result = audit([forecast], [score])
        self.assertEqual(result["results"][0]["forecasts_different_from_persistence"], 0)
        self.assertFalse(result["results"][0]["model_differentiation_observed"])
        self.assertEqual(result["results"][0]["improvement_pct"], 0.0)

    def test_rejects_early_score(self):
        row = dict(self.score, scored_at_utc=self.forecast["issued_at_utc"])
        with self.assertRaisesRegex(ValueError, "before target close"):
            audit([self.forecast], [row])

    def test_rejects_incorrect_error(self):
        row = dict(self.score, model_absolute_error_usd=0.0)
        with self.assertRaisesRegex(ValueError, "Incorrect model score"):
            audit([self.forecast], [row])

    def test_rejects_duplicate_forecast(self):
        with self.assertRaisesRegex(ValueError, "Duplicate forecast"):
            audit([self.forecast, self.forecast], [self.score])


if __name__ == "__main__":
    unittest.main()
