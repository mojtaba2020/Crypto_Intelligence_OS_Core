#!/usr/bin/env python3
"""Point-in-time-safe multi-scale OHLCV features for daily/weekly/monthly research."""

from __future__ import annotations

import math
import statistics

WINDOWS = {
    "daily": (3, 7, 14, 30, 90, 180, 365),
    "weekly": (2, 4, 8, 13, 26, 52),
    "monthly": (2, 3, 6, 12, 24, 36),
}


def feature_names(family: str) -> tuple[str, ...]:
    windows = WINDOWS[family]
    names = [f"log_return_{window}" for window in windows]
    names += [f"realized_vol_{window}" for window in windows if window >= 3]
    names += [
        "drawdown_from_running_high",
        "range_pct",
        "close_location",
        "body_pct",
        "log_volume_vs_median",
    ]
    return tuple(names)


def feature_vector(
    candles: list[dict[str, float]],
    origin: int,
    family: str,
) -> list[float]:
    windows = WINDOWS[family]
    longest = max(windows)
    if origin < longest or origin >= len(candles):
        raise ValueError(f"{family} feature origin requires {longest} completed past bars")

    current = float(candles[origin]["close"])
    if current <= 0:
        raise ValueError("Close must be positive")

    values = [math.log(current / float(candles[origin - window]["close"])) for window in windows]
    returns = [
        math.log(float(candles[i]["close"]) / float(candles[i - 1]["close"]))
        for i in range(origin - longest + 1, origin + 1)
    ]
    for window in windows:
        if window >= 3:
            values.append(statistics.pstdev(returns[-window:]))

    history = candles[origin - longest : origin + 1]
    running_high = max(float(row["high"]) for row in history)
    candle = candles[origin]
    high = float(candle["high"])
    low = float(candle["low"])
    open_price = float(candle["open"])
    volume = float(candle["volume"])
    volumes = [float(row["volume"]) for row in history]
    median_volume = statistics.median(volumes)

    values.extend(
        [
            current / running_high - 1.0,
            (high - low) / current,
            (current - low) / (high - low) if high > low else 0.5,
            (current - open_price) / open_price,
            math.log((volume + 1e-12) / (median_volume + 1e-12)),
        ]
    )
    if len(values) != len(feature_names(family)) or any(not math.isfinite(x) for x in values):
        raise ValueError("Invalid multi-timeframe feature vector")
    return values
