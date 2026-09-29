from __future__ import annotations

import math

import pytest
from scripts.multitimeframe_features_v3 import (
    feature_names,
    feature_vector,
    has_valid_feature_history,
    has_valid_forecast_target,
    is_temporally_valid_sample,
)


def _candles(n: int) -> list[dict[str, float]]:
    rows = []
    for i in range(n):
        close = 100.0 * math.exp(0.001 * i + 0.01 * math.sin(i / 7))
        rows.append(
            {
                "open": close * 0.999,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": 1000.0 + i,
            }
        )
    return rows


@pytest.mark.parametrize(
    ("family", "origin"),
    [("daily", 365), ("weekly", 52), ("monthly", 36)],
)
def test_feature_vector_is_finite_and_matches_schema(family: str, origin: int) -> None:
    values = feature_vector(_candles(origin + 10), origin, family)
    assert len(values) == len(feature_names(family))
    assert all(math.isfinite(value) for value in values)


def test_feature_vector_is_point_in_time_safe() -> None:
    candles = _candles(400)
    before = feature_vector(candles, 365, "daily")
    for row in candles[366:]:
        row["close"] *= 100.0
        row["high"] *= 100.0
        row["low"] *= 100.0
        row["open"] *= 100.0
        row["volume"] *= 100.0
    after = feature_vector(candles, 365, "daily")
    assert before == after


def test_unknown_family_fails_closed() -> None:
    with pytest.raises(KeyError):
        feature_names("hourly")


def test_gap_safe_sample_rejects_missing_daily_period() -> None:
    candles = _candles(370)
    for i, row in enumerate(candles):
        row["timestamp"] = float(i * 86_400)
    assert is_temporally_valid_sample(candles, "daily", 365, 1)
    candles[200]["timestamp"] += 86_400
    assert not is_temporally_valid_sample(candles, "daily", 365, 1)


def test_gap_safe_sample_rejects_target_crossing_gap() -> None:
    candles = _candles(370)
    for i, row in enumerate(candles):
        row["timestamp"] = float(i * 86_400)
    candles[366]["timestamp"] += 86_400
    assert not is_temporally_valid_sample(candles, "daily", 365, 1)


def test_feature_and_target_continuity_are_checked_independently() -> None:
    candles = _candles(800)
    for i, row in enumerate(candles):
        row["timestamp"] = float(i * 86_400)
    # An old unrelated gap must not poison a later otherwise-valid sample.
    candles[10]["timestamp"] += 86_400
    assert has_valid_feature_history(candles, "daily", 700)
    assert has_valid_forecast_target(candles, "daily", 700, 3)
    assert is_temporally_valid_sample(candles, "daily", 700, 3)


def test_feature_history_gap_does_not_invalidate_unrelated_target_logic() -> None:
    candles = _candles(800)
    for i, row in enumerate(candles):
        row["timestamp"] = float(i * 86_400)
    candles[500]["timestamp"] += 86_400
    assert not has_valid_feature_history(candles, "daily", 700)
    assert has_valid_forecast_target(candles, "daily", 700, 3)
    assert not is_temporally_valid_sample(candles, "daily", 700, 3)
