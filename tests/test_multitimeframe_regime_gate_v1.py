from __future__ import annotations

import math

import pytest

from scripts.multitimeframe_regime_gate_v1 import classify_regimes, regime_gate


def _candles(n: int) -> list[dict[str, float]]:
    rows = []
    for i in range(n):
        close = 100.0 * math.exp(0.0004 * i + 0.03 * math.sin(i / 13))
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


def test_regime_classification_is_point_in_time_safe() -> None:
    candles = _candles(800)
    origin = 600
    baseline = classify_regimes(candles, origin, "daily")
    mutated = [dict(row) for row in candles]
    for i in range(origin + 1, len(mutated)):
        mutated[i]["close"] *= 100.0
        mutated[i]["high"] *= 100.0
        mutated[i]["low"] *= 100.0
    assert classify_regimes(mutated, origin, "daily") == baseline


def test_regime_gate_is_pre_specified_and_never_promotes() -> None:
    candles = _candles(900)
    origins = list(range(500, 800, 10))
    challenger = [0.01 + 0.001 * math.sin(i) for i in range(len(origins))]
    baseline = [value + 0.002 for value in challenger]
    report = regime_gate(
        candles, origins, challenger, baseline, "daily", minimum_samples=2
    )
    assert set(report["regimes"]) == {
        "uptrend",
        "downtrend",
        "high_volatility",
        "low_volatility",
    }
    assert report["policy"] == "pre_specified_descriptive_gate_no_subgroup_selection"
    assert report["production_promotion"] is False


def test_mismatched_inputs_fail_closed() -> None:
    with pytest.raises(ValueError, match="identical lengths"):
        regime_gate(_candles(800), [500], [0.1, 0.2], [0.1], "daily")
