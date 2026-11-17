"""Synthetic sanity checks; no live API fetch, no claim of forecasting skill."""

from __future__ import annotations

import json
import math
import unittest
from datetime import timedelta
from typing import ClassVar
from unittest.mock import patch

from scripts.btc4h_challenger_october_replay import (
    END,
    START,
    build_rows,
    evaluate_retrospective,
    fetch_buckets,
)


class DummyModel:
    sizes: ClassVar[list[int]] = []

    def fit(self, x: list[list[float]], y: list[float]) -> None:
        self.sizes.append(len(x))
        assert len(x) == len(y)

    def predict(self, x: list[list[float]]) -> list[float]:
        assert len(x) == 1
        return [0.0002]


def synthetic_candles():
    hourly = {}
    current = START - timedelta(hours=25)
    index = 0
    while current < END:
        price = 60_000 + index * 0.31 + 14.0 * math.sin(index / 5)
        volume = 2.0 + index % 11 * 0.03
        hourly[current] = (price, volume)
        current += timedelta(hours=1)
        index += 1
    targets = {}
    origin = START
    while origin < END:
        target = origin + timedelta(hours=4, minutes=10)
        targets[target] = (60_020.0 + index * 0.1, 0.1)
        origin += timedelta(hours=4)
        index += 1
    return hourly, targets


class DevelopmentReplayTests(unittest.TestCase):
    def setUp(self) -> None:
        DummyModel.sizes.clear()

    def test_only_complete_exposed_window_origins(self):
        hourly, targets = synthetic_candles()
        rows, counters = build_rows(hourly, targets)
        self.assertEqual(len(rows), 102)
        self.assertEqual(sum(counters.values()), 0)
        self.assertEqual(rows[0]["origin"], START)
        self.assertEqual(rows[-1]["origin"], END - timedelta(hours=4))
        self.assertTrue(all(len(row["x"]) == 3 for row in rows))

    def test_matured_training_skips_immediately_previous_label(self):
        hourly, targets = synthetic_candles()
        rows, _ = build_rows(hourly, targets)
        report = evaluate_retrospective(rows, model_factory=lambda name: DummyModel())
        self.assertEqual(report["evaluation_count"], 24)
        self.assertEqual(report["earliest_mature_training_count"], 30)
        self.assertEqual(DummyModel.sizes[:5], [30] * 5)
        self.assertEqual(len(DummyModel.sizes), 24 * 5)
        self.assertFalse(report["historical_feature_vintage_authenticated"])
        self.assertFalse(report["original_forecast_issuance_exists"])
        self.assertEqual(len(report["model_metrics"]), 6)

    def test_missing_candles_do_not_get_interpolated(self):
        hourly, targets = synthetic_candles()
        missing_origin = START + timedelta(hours=16)
        targets.pop(missing_origin + timedelta(hours=4, minutes=10))
        rows, counters = build_rows(hourly, targets)
        self.assertEqual(len(rows), 101)
        self.assertEqual(counters["missing_target"], 1)
        self.assertEqual(counters["missing_hourly"], 0)

    def test_wrong_window_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "pinned"):
            build_rows({}, {}, start=START, end=END + timedelta(days=1))

    def test_no_source_network_from_invalid_bounds(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            fetch_buckets(START, END + timedelta(days=6), 3600)

    def test_actual_missing_past_maturity_blocks_training(self):
        hourly, targets = synthetic_candles()
        rows, _ = build_rows(hourly, targets)
        for row in rows:
            row["target_close"] = END + timedelta(days=1)
        with self.assertRaisesRegex(ValueError, "no folds"):
            evaluate_retrospective(rows, model_factory=lambda name: DummyModel())

    def test_invalid_response_is_not_silently_accepted(self):
        start = START
        end = START + timedelta(hours=2)

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                pass

            def geturl(self):
                return "https://api.exchange.coinbase.com/products/BTC-USD/candles"

            def read(self, *_):
                return json.dumps([[int(start.timestamp()), 1, 2, 1, -1, 3]]).encode()

        with patch("urllib.request.urlopen", return_value=Response()):
            with self.assertRaisesRegex(ValueError, "positive"):
                fetch_buckets(start, end, 3600)

    def test_redirect_outside_publisher_is_rejected(self):
        start = START
        end = START + timedelta(hours=2)

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                pass

            def geturl(self):
                return "https://example.org/evil"

            def read(self, *_):
                return b"[]"

        with patch("urllib.request.urlopen", return_value=Response()):
            with self.assertRaisesRegex(ValueError, "redirect"):
                fetch_buckets(start, end, 3600)


if __name__ == "__main__":
    unittest.main()
