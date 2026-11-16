"""Synthetic-only safeguards for the isolated four-hour challenger tournament."""

from __future__ import annotations

import math
import unittest
from datetime import UTC, datetime, timedelta

from scripts.btc4h_challenger_tournament import (
    ALL_MODELS,
    CANDIDATES,
    MAX_EVAL,
    evaluate,
    validate_rows,
)

START = datetime(2026, 1, 1, tzinfo=UTC)


def stamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def example(index: int) -> dict:
    origin = START + timedelta(hours=4 * index)
    m = (index % 7 - 3) * 0.001
    v = (index % 5 - 2) * 0.1
    reference = 60000.0 + index
    return {
        "origin_utc": stamp(origin),
        "issued_at_utc": stamp(origin + timedelta(minutes=10)),
        "features_available_at_utc": stamp(origin + timedelta(minutes=9)),
        "target_5m_close_utc": stamp(origin + timedelta(hours=4, minutes=15)),
        "target_first_observed_at_utc": stamp(origin + timedelta(hours=4, minutes=20)),
        "origin_reference_close_usd": reference,
        "actual_close_usd": reference * math.exp(0.002 if index % 2 else -0.002),
        "features": {
            "momentum_4h": m,
            "volume_surprise": v,
            "momentum_times_volume": m * v,
        },
    }


class FakeEstimator:
    seen_training_sizes: list[int] = []

    def fit(self, x: list[list[float]], y: list[float]) -> None:
        self.seen_training_sizes.append(len(y))
        assert len(x) == len(y)
        assert all(len(row) == 3 for row in x)

    def predict(self, x: list[list[float]]) -> list[float]:
        assert len(x) == 1
        return [0.0001]


class ChallengerTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeEstimator.seen_training_sizes.clear()

    def test_five_frozen_models_plus_persistence(self):
        self.assertEqual(len(CANDIDATES), 5)
        self.assertEqual(len(ALL_MODELS), 6)
        self.assertEqual(ALL_MODELS[0], "persistence")

    def test_offline_comparison_uses_only_mature_prior_training(self):
        rows = [example(i) for i in range(40)]
        report = evaluate(rows, model_factory=lambda name: FakeEstimator())
        self.assertEqual(report["study"], "RETROSPECTIVE_OFFLINE_NOT_LIVE")
        self.assertEqual(report["status"], "DESCRIPTIVE_ONLY_NO_PROMOTION")
        self.assertTrue(report["no_model_winner_authorized"])
        self.assertEqual(report["evaluated_rows"], 9)
        self.assertEqual(report["evaluated_origins"][0]["origin_utc"], rows[31]["origin_utc"])
        self.assertEqual(report["evaluated_origins"][0]["mature_training_rows"], 30)
        self.assertEqual(FakeEstimator.seen_training_sizes[:5], [30] * 5)
        self.assertEqual(set(report["models"]), set(ALL_MODELS))
        self.assertIsNone(report["models"]["persistence"]["direction_accuracy_conditional"])

    def test_late_labels_are_not_leaked_to_training(self):
        rows = [example(i) for i in range(40)]
        for row in rows:
            when = START + timedelta(days=30)
            row["target_first_observed_at_utc"] = stamp(when)
        report = evaluate(rows, model_factory=lambda name: FakeEstimator())
        self.assertEqual(report["status"], "INSUFFICIENT_MATURE_DATA")
        self.assertEqual(report["evaluated_rows"], 0)
        self.assertEqual(FakeEstimator.seen_training_sizes, [])

    def test_missing_slot_count_not_hidden(self):
        rows = [example(i) for i in range(35)]
        rows.pop(10)
        report = evaluate(rows, model_factory=lambda name: FakeEstimator())
        self.assertEqual(report["missing_origin_slots"], 1)
        self.assertEqual(report["expected_slots_between_bounds"], 35)

    def test_evaluation_cost_cap(self):
        report = evaluate([example(i) for i in range(110)], model_factory=lambda name: FakeEstimator())
        self.assertEqual(report["evaluated_rows"], MAX_EVAL)
        self.assertEqual(len(FakeEstimator.seen_training_sizes), 5 * MAX_EVAL)

    def test_duplicate_and_unsorted_origins_rejected(self):
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            validate_rows([example(0), example(0)])
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            validate_rows([example(1), example(0)])

    def test_cannot_use_features_first_seen_after_issue(self):
        rows = [example(0), example(1)]
        rows[1]["features_available_at_utc"] = stamp(START + timedelta(hours=4, minutes=12))
        rows[1]["issued_at_utc"] = stamp(START + timedelta(hours=4, minutes=10))
        with self.assertRaisesRegex(ValueError, "features were not available"):
            validate_rows(rows)

    def test_cannot_backdate_a_late_issuance(self):
        rows = [example(0), example(1)]
        rows[1]["issued_at_utc"] = stamp(START + timedelta(hours=4, minutes=55))
        with self.assertRaisesRegex(ValueError, "on-time"):
            validate_rows(rows)

    def test_wrong_target_or_early_observation_is_rejected(self):
        rows = [example(0), example(1)]
        rows[1]["target_5m_close_utc"] = stamp(START + timedelta(hours=8, minutes=10))
        with self.assertRaisesRegex(ValueError, "target bar close"):
            validate_rows(rows)
        rows = [example(0), example(1)]
        rows[1]["target_first_observed_at_utc"] = stamp(START + timedelta(hours=8, minutes=14))
        with self.assertRaisesRegex(ValueError, "outcome reported"):
            validate_rows(rows)

    def test_unsafe_shape_and_nonfinite_features_are_rejected(self):
        rows = [example(0), example(1)]
        rows[0]["new_outcome_leak"] = 1
        with self.assertRaisesRegex(ValueError, "unexpected"):
            validate_rows(rows)
        rows = [example(0), example(1)]
        rows[0]["features"]["momentum_times_volume"] = 1.0
        with self.assertRaisesRegex(ValueError, "interaction"):
            validate_rows(rows)
        rows = [example(0), example(1)]
        rows[0]["features"]["momentum_4h"] = float("nan")
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            validate_rows(rows)

    def test_reject_naive_utc_and_nan_prices(self):
        rows = [example(0), example(1)]
        rows[0]["issued_at_utc"] = "2026-01-01T00:10:00"
        with self.assertRaisesRegex(ValueError, "UTC"):
            validate_rows(rows)
        rows = [example(0), example(1)]
        rows[0]["actual_close_usd"] = float("nan")
        with self.assertRaisesRegex(ValueError, "finite"):
            validate_rows(rows)


if __name__ == "__main__":
    unittest.main()
