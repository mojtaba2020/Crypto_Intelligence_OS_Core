#!/usr/bin/env python3
"""Transparent point-in-time hourly market regime classifier V1."""

from __future__ import annotations

import math
import statistics


def classify_regime(candles: list[dict[str, float]], origin: int) -> str:
    """Classify using only information available at or before origin."""
    if origin < 168 or origin >= len(candles):
        raise ValueError("Regime origin requires 168 completed past hourly candles")

    closes = [float(candles[i]["close"]) for i in range(origin - 168, origin + 1)]
    if any(not math.isfinite(x) or x <= 0 for x in closes):
        raise ValueError("Invalid close history")

    ret_24h = math.log(closes[-1] / closes[-25])
    hourly_returns = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
    vol_24h = statistics.pstdev(hourly_returns[-24:])
    historical_vol_24h = [
        statistics.pstdev(hourly_returns[i - 24 : i])
        for i in range(24, len(hourly_returns) + 1)
    ]
    median_vol = statistics.median(historical_vol_24h)
    volatility = "high_vol" if vol_24h > median_vol else "low_vol"

    # A small neutral band avoids calling tiny 24h moves trends.
    if ret_24h > 0.01:
        trend = "up"
    elif ret_24h < -0.01:
        trend = "down"
    else:
        trend = "range"

    return f"{trend}__{volatility}"
