from __future__ import annotations

import math

import pytest
from scripts.multitimeframe_features_v3 import feature_names, feature_vector


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
