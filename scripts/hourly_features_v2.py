#!/usr/bin/env python3
"""Point-in-time-safe shared hourly BTC feature engineering V2."""

from __future__ import annotations

import math
import statistics

LAGS = (1, 2, 3, 6, 12, 24, 48, 72, 168)
VOL_WINDOWS = (6, 12, 24, 72)
VOLUME_WINDOWS = (6, 24, 72)


def feature_names() -> tuple[str, ...]:
    names = [f"log_return_{lag}h" for lag in LAGS]
    names += [f"realized_vol_{window}h" for window in VOL_WINDOWS]
    names += [
        "candle_body_pct",
        "high_low_range_pct",
        "close_location",
        "range_mean_6h",
        "range_mean_24h",
    ]
    names += [f"log_volume_ratio_{window}h" for window in VOLUME_WINDOWS]
    names += ["volume_return_corr_24h"]
    return tuple(names)


def _validate(candles: list[dict[str, float]], origin: int) -> None:
    if origin < 168 or origin >= len(candles):
        raise ValueError("Feature origin requires 168 completed past hourly candles")
    required = ("open", "high", "low", "close", "volume")
    for candle in candles[origin - 168 : origin + 1]:
        if any(not math.isfinite(float(candle[key])) for key in required):
            raise ValueError("Non-finite OHLCV value")
        if min(float(candle[key]) for key in ("open", "high", "low", "close")) <= 0:
            raise ValueError("OHLC prices must be positive")
        if float(candle["volume"]) < 0:
            raise ValueError("Volume cannot be negative")


def feature_vector(candles: list[dict[str, float]], origin: int) -> list[float]:
    """Build features using only candles at or before origin."""
    _validate(candles, origin)
    current = float(candles[origin]["close"])
    values = [
        math.log(current / float(candles[origin - lag]["close"]))
        for lag in LAGS
    ]

    hourly_returns = [
        math.log(float(candles[i]["close"]) / float(candles[i - 1]["close"]))
        for i in range(origin - 167, origin + 1)
    ]
    for window in VOL_WINDOWS:
        values.append(statistics.pstdev(hourly_returns[-window:]))

    candle = candles[origin]
    open_price = float(candle["open"])
    high = float(candle["high"])
    low = float(candle["low"])
    values.extend(
        [
            (current - open_price) / open_price,
            (high - low) / current,
            (current - low) / (high - low) if high > low else 0.5,
        ]
    )

    ranges = [
        (float(candles[i]["high"]) - float(candles[i]["low"]))
        / float(candles[i]["close"])
        for i in range(origin - 23, origin + 1)
    ]
    values.extend([statistics.mean(ranges[-6:]), statistics.mean(ranges)])

    current_volume = float(candle["volume"])
    for window in VOLUME_WINDOWS:
        past = [float(candles[i]["volume"]) for i in range(origin - window + 1, origin + 1)]
        mean_volume = statistics.mean(past)
        values.append(math.log((current_volume + 1e-12) / (mean_volume + 1e-12)))

    returns_24 = hourly_returns[-24:]
    volumes_24 = [
        math.log(float(candles[i]["volume"]) + 1e-12)
        for i in range(origin - 23, origin + 1)
    ]
    mean_r = statistics.mean(returns_24)
    mean_v = statistics.mean(volumes_24)
    covariance = statistics.mean(
        (r - mean_r) * (v - mean_v)
        for r, v in zip(returns_24, volumes_24, strict=True)
    )
    std_r = statistics.pstdev(returns_24)
    std_v = statistics.pstdev(volumes_24)
    values.append(covariance / (std_r * std_v) if std_r and std_v else 0.0)

    if len(values) != len(feature_names()) or any(not math.isfinite(v) for v in values):
        raise ValueError("Invalid feature vector")
    return values
