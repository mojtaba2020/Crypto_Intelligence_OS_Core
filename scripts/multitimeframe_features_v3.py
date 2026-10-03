#!/usr/bin/env python3
"""Point-in-time-safe multi-scale OHLCV features for daily/weekly/monthly research."""

from __future__ import annotations

import math
import statistics
from datetime import UTC, datetime
from itertools import pairwise

WINDOWS = {
    "daily": (3, 7, 14, 30, 90, 180, 365),
    "weekly": (2, 4, 8, 13, 26, 52),
    "monthly": (2, 3, 6, 12, 24, 36),
}

REGIME_WINDOWS = {
    "daily": (7, 30, 90),
    "weekly": (4, 13, 26),
    "monthly": (3, 6, 12),
}


def _next_period_timestamp(timestamp: int, family: str) -> int:
    if family == "daily":
        return timestamp + 86_400
    if family == "weekly":
        return timestamp + 604_800
    if family == "monthly":
        current = datetime.fromtimestamp(timestamp, tz=UTC)
        year = current.year + (1 if current.month == 12 else 0)
        month = 1 if current.month == 12 else current.month + 1
        return int(datetime(year, month, 1, tzinfo=UTC).timestamp())
    raise KeyError(family)


def _is_contiguous(candles: list[dict[str, float]], family: str, start: int, end: int) -> bool:
    """Return whether inclusive [start, end] follows the exact declared calendar cadence."""
    if start < 0 or end >= len(candles) or start > end:
        return False
    needed = candles[start : end + 1]
    if not all("timestamp" in row for row in needed):
        return True
    if any(row.get("is_complete") is False for row in needed):
        return False
    timestamps = [int(row["timestamp"]) for row in needed]
    return all(
        right == _next_period_timestamp(left, family) for left, right in pairwise(timestamps)
    )


def has_valid_feature_history(
    candles: list[dict[str, float]],
    family: str,
    origin: int,
) -> bool:
    """Feature history must be continuous, independently for each candidate origin."""
    longest = max(WINDOWS[family])
    return origin >= longest and _is_contiguous(candles, family, origin - longest, origin)


def has_valid_forecast_target(
    candles: list[dict[str, float]],
    family: str,
    origin: int,
    horizon: int,
) -> bool:
    """Forecast target must be continuous from origin through maturity."""
    return horizon > 0 and _is_contiguous(candles, family, origin, origin + horizon)


def is_temporally_valid_sample(
    candles: list[dict[str, float]],
    family: str,
    origin: int,
    horizon: int,
) -> bool:
    """Require valid feature history and target, without coupling unrelated gaps."""
    return has_valid_feature_history(candles, family, origin) and has_valid_forecast_target(
        candles, family, origin, horizon
    )


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
    fast, medium, slow = REGIME_WINDOWS[family]
    names += [
        f"trend_close_vs_sma_{fast}",
        f"trend_close_vs_sma_{medium}",
        f"trend_sma_{fast}_vs_{medium}",
        f"trend_sma_{medium}_vs_{slow}",
        f"vol_ratio_{fast}_vs_{medium}",
        f"vol_ratio_{medium}_vs_{slow}",
        f"range_position_{medium}",
    ]
    return tuple(names)


def _mean_close(candles: list[dict[str, float]], origin: int, window: int) -> float:
    return statistics.fmean(float(row["close"]) for row in candles[origin - window + 1 : origin + 1])


def _realized_vol(candles: list[dict[str, float]], origin: int, window: int) -> float:
    returns = [
        math.log(float(candles[i]["close"]) / float(candles[i - 1]["close"]))
        for i in range(origin - window + 1, origin + 1)
    ]
    return statistics.pstdev(returns)


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

    fast, medium, slow = REGIME_WINDOWS[family]
    sma_fast = _mean_close(candles, origin, fast)
    sma_medium = _mean_close(candles, origin, medium)
    sma_slow = _mean_close(candles, origin, slow)
    vol_fast = _realized_vol(candles, origin, fast)
    vol_medium = _realized_vol(candles, origin, medium)
    vol_slow = _realized_vol(candles, origin, slow)
    medium_rows = candles[origin - medium + 1 : origin + 1]
    medium_high = max(float(row["high"]) for row in medium_rows)
    medium_low = min(float(row["low"]) for row in medium_rows)
    range_position = (
        (current - medium_low) / (medium_high - medium_low)
        if medium_high > medium_low
        else 0.5
    )

    values.extend(
        [
            current / sma_fast - 1.0,
            current / sma_medium - 1.0,
            sma_fast / sma_medium - 1.0,
            sma_medium / sma_slow - 1.0,
            vol_fast / (vol_medium + 1e-12),
            vol_medium / (vol_slow + 1e-12),
            range_position,
        ]
    )
    if len(values) != len(feature_names(family)) or any(not math.isfinite(x) for x in values):
        raise ValueError("Invalid multi-timeframe feature vector")
    return values
