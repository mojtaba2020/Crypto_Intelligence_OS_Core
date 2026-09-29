from __future__ import annotations

import math

from scripts import attribute_hourly_candle_features_v2 as attribution


def _candles(n: int = 420) -> list[dict[str, float]]:
    rows = []
    for i in range(n):
        close = 100.0 * math.exp(0.0005 * i + 0.002 * math.sin(i / 9))
        open_price = close * (1.0 - 0.0008 * math.sin(i / 5))
        high = max(open_price, close) * 1.002
        low = min(open_price, close) * 0.998
        rows.append(
            {
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": 1000.0 + (i % 17) * 10.0,
            }
        )
    return rows


def test_cached_evaluate_matches_uncached() -> None:
    candles = _candles()
    indices = (13, 16, 17)

    uncached = attribution._evaluate(
        candles,
        indices,
        train_min=360,
        step=24,
        horizon=1,
    )

    closes = [float(c["close"]) for c in candles]
    cache = [
        attribution.feature_vector(candles, origin) if origin >= 168 else None
        for origin in range(len(candles))
    ]
    cached = attribution._evaluate(
        candles,
        indices,
        train_min=360,
        step=24,
        horizon=1,
        feature_cache=cache,
        closes=closes,
    )

    assert cached == uncached


def test_tournament_computes_each_origin_feature_once(monkeypatch) -> None:
    candles = _candles()
    original = attribution.feature_vector
    calls = 0

    def counted(candles_arg: list[dict[str, float]], origin: int) -> list[float]:
        nonlocal calls
        calls += 1
        return original(candles_arg, origin)

    monkeypatch.setattr(attribution, "feature_vector", counted)
    report = attribution.tournament(candles, train_min=360, step=24)

    assert report["status"] == "CANDLE_FEATURE_ATTRIBUTION_STANDARDIZED_V1"
    assert calls == len(candles) - 168
