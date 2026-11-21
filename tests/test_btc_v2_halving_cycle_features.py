"""Synthetic date-boundary tests for label-blind BTC halving-cycle features."""

from __future__ import annotations

import unittest

from scripts.btc_v2_halving_cycle_features import halving_cycle_snapshot


class HalvingCycleTests(unittest.TestCase):
    def test_no_first_halving_before_2012_is_missing_not_zero(self):
        for cutoff in ("2011-10-01T12:00:00Z", "2012-11-27T23:59:00Z"):
            with self.subTest(cutoff=cutoff):
                row = halving_cycle_snapshot(cutoff)
                self.assertIsNone(row["value"])
                self.assertFalse(row["has_value"])
                self.assertFalse(row["train_eligible"])

    def test_first_halving_same_day_not_leaked_by_date_only_calendar(self):
        row = halving_cycle_snapshot("2012-11-28T23:59:00Z")
        self.assertTrue(row["same_day_halving_excluded"])
        self.assertIsNone(row["value"])

    def test_first_halving_available_on_following_utc_day(self):
        row = halving_cycle_snapshot("2012-11-29T00:00:00Z")
        self.assertEqual(row["value"], 1.0)
        self.assertEqual(row["last_conservatively_known_halving_date"], "2012-11-28")
        self.assertFalse(row["independent_chain_timestamp_verified"])

    def test_second_halving_same_day_uses_prior_event_not_future(self):
        row = halving_cycle_snapshot("2016-07-09T01:00:00Z")
        self.assertTrue(row["same_day_halving_excluded"])
        self.assertEqual(row["last_conservatively_known_halving_date"], "2012-11-28")

    def test_new_2024_halving_only_after_date_has_elapsed(self):
        same_day = halving_cycle_snapshot("2024-04-20T23:55:00Z")
        next_day = halving_cycle_snapshot("2024-04-21T00:00:00Z")
        self.assertEqual(same_day["last_conservatively_known_halving_date"], "2020-05-11")
        self.assertEqual(next_day["last_conservatively_known_halving_date"], "2024-04-20")
        self.assertEqual(next_day["value"], 1.0)

    def test_future_halving_not_invented(self):
        row = halving_cycle_snapshot("2026-11-20T20:00:00Z")
        self.assertEqual(row["last_conservatively_known_halving_date"], "2024-04-20")
        self.assertGreater(row["value"], 0)
        self.assertFalse(row["train_eligible"])

    def test_utc_enforced(self):
        for invalid in ("2024-04-21T00:00:00", "2024-04-21T00:00:00-05:00", "invalid"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    halving_cycle_snapshot(invalid)

    def test_nontext_cutoff_rejected(self):
        with self.assertRaises(ValueError):
            halving_cycle_snapshot(None)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
