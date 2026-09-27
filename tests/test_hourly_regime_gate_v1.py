"""Tests for point-in-time hourly regime research gates."""

import math

from scripts.hourly_regime_v1 import classify_regime
from scripts.paired_block_bootstrap import paired_block_bootstrap


def _candles_from_returns(returns: list[float]) -> list[dict[str, float]]:
    closes = [100.0]
    for value in returns:
        closes.append(closes[-1] * math.exp(value))
    return [
        {
            "open": close * 0.999,
            "high": close * 1.002,
            "low": close * 0.998,
            "close": close,
            "volume": 1000.0 + i,
        }
        for i, close in enumerate(closes)
    ]


def test_regime_is_point_in_time_and_ignores_future_mutation():
    candles = _candles_from_returns([0.002] * 220)
    origin = 168
    before = classify_regime(candles, origin)
    for row in candles[origin + 1 :]:
        row["close"] *= 100.0
    assert classify_regime(candles, origin) == before


def test_regime_classifies_trend_band_and_low_volatility():
    assert classify_regime(_candles_from_returns([0.002] * 168), 168) == "up__low_vol"
    assert classify_regime(_candles_from_returns([-0.002] * 168), 168) == "down__low_vol"
    assert classify_regime(_candles_from_returns([0.0] * 168), 168) == "range__low_vol"


def test_regime_detects_recent_high_volatility_without_future_data():
    returns = [0.0] * 144 + [0.03 if i % 2 == 0 else -0.03 for i in range(24)]
    candles = _candles_from_returns(returns)
    assert classify_regime(candles, 168) == "range__high_vol"


def test_paired_block_bootstrap_passes_clear_edge_and_is_deterministic():
    model = [0.01] * 60
    baseline = [0.02] * 60
    first = paired_block_bootstrap(model, baseline, repetitions=500)
    second = paired_block_bootstrap(model, baseline, repetitions=500)
    assert first == second
    assert first["gate"] == "PASS"
    assert first["ci_95"][0] > 0


def test_paired_block_bootstrap_rejects_no_edge():
    losses = [0.01] * 60
    report = paired_block_bootstrap(losses, losses, repetitions=500)
    assert report["gate"] == "FAIL"
    assert report["ci_95"] == [0.0, 0.0]


def test_regime_volatility_reference_excludes_current_estimate():
    returns = [0.001 if i % 2 == 0 else -0.001 for i in range(144)]
    returns += [0.002 if i % 2 == 0 else -0.002 for i in range(24)]
    candles = _candles_from_returns(returns)
    origin = 168

    closes = [float(candles[i]["close"]) for i in range(origin - 168, origin + 1)]
    hourly_returns = [
        math.log(closes[i] / closes[i - 1])
        for i in range(1, len(closes))
    ]
    current_vol = __import__("statistics").pstdev(hourly_returns[-24:])
    historical = [
        __import__("statistics").pstdev(hourly_returns[i - 24 : i])
        for i in range(24, len(hourly_returns))
    ]
    assert current_vol > __import__("statistics").median(historical)
    assert classify_regime(candles, origin).endswith("__high_vol")
