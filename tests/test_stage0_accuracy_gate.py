"""Offline tests for the stage-zero accuracy gate; no network required."""
import json
import math
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.stage0_accuracy_gate import HORIZONS, evaluate, load_candles


class AccuracyGateTests(unittest.TestCase):
    def setUp(self):
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        self.rows = [(start + timedelta(hours=i), 50000.0 * math.exp(0.0001 * i + 0.003 * math.sin(i / 13))) for i in range(1000)]

    def test_all_horizons_return_finite_metrics(self):
        for h in HORIZONS:
            result = evaluate(self.rows, h)
            self.assertEqual(result["horizon_hours"], h)
            self.assertEqual(result["test_examples"], 96)
            self.assertTrue(math.isfinite(result["test_model_mae_usd"]))
            self.assertTrue(math.isfinite(result["test_persistence_mae_usd"]))

    def test_reject_missing_candles(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "candles.json"
            path.write_text(json.dumps([[t.isoformat(), p] for t, p in self.rows if t != self.rows[100][0]]))
            with self.assertRaisesRegex(ValueError, "Missing or duplicate"):
                load_candles(path)

    def test_reject_non_utc(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "candles.json"
            path.write_text(json.dumps([[t.replace(tzinfo=None).isoformat(), p] for t, p in self.rows]))
            with self.assertRaisesRegex(ValueError, "UTC"):
                load_candles(path)


if __name__ == "__main__":
    unittest.main()
