#!/usr/bin/env python3
"""Wave-3 FEATURE-03 pure, synthetic-testable daily proposal (NOT model-integrated).

Implements Issue #76's unique seven-comparison volume-supported reversal share.
It has no provider, filesystem, model-fitting or trading entry point. It is not
an approved feature for Stage-6 inference, model selection or production.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

SECONDS_PER_DAY = 86_400
LOOKBACK_BARS = 9
REVERSAL_COMPARISONS = 7


def daily_volume_supported_reversal_share(
    candles: Sequence[Mapping[str, object]],
    origin: int,
    *,
    asof_timestamp: int,
    source_interval_seconds: int,
) -> float:
    """Return one point-in-time scalar from exactly nine finalized UTC daily bars.

    If r_i=log(C_i/C_(i-1)) and w_i=min(V_i,V_(i-1)), this computes
       sum(i=t-6..t) w_i * 1(r_i*r_(i-1)<0) / sum(i=t-6..t) w_i.

    Timestamp is the canonical daily UTC bar opening. Each bar must include
    source_finalized_at UTC at or after its close and no later than query as-of.
    Source counts and units are assertions, not proof of publication or trust.
    """
    if type(origin) is not int or origin < LOOKBACK_BARS - 1 or origin >= len(candles):
        raise ValueError("Exactly nine trailing daily bars are required")
    if type(asof_timestamp) is not int or asof_timestamp <= 0:
        raise ValueError("Invalid as-of timestamp")
    if type(source_interval_seconds) is not int or source_interval_seconds not in (
        3_600,
        86_400,
    ):
        raise ValueError("Only audited hourly/daily source periods are supported")

    expected_source_count = SECONDS_PER_DAY // source_interval_seconds
    window = candles[origin - LOOKBACK_BARS + 1 : origin + 1]
    if len(window) != LOOKBACK_BARS:
        raise ValueError("Incomplete nine-bar history")

    closes: list[float] = []
    volumes: list[float] = []
    previous_open: int | None = None
    approved_volume_unit: str | None = None
    for row in window:
        if not isinstance(row, Mapping) or row.get("is_complete") is not True:
            raise ValueError("Incomplete or malformed daily bar")
        opening = row.get("timestamp")
        finalized = row.get("source_finalized_at")
        if (
            type(opening) is not int
            or opening < 0
            or opening % SECONDS_PER_DAY
            or (previous_open is not None and opening != previous_open + SECONDS_PER_DAY)
        ):
            raise ValueError("Noncanonical, duplicated or missing UTC daily bar")
        previous_open = opening
        if (
            type(finalized) is not int
            or finalized < opening + SECONDS_PER_DAY
            or finalized > asof_timestamp
        ):
            raise ValueError("Daily bar is not finalized/available at requested as-of")
        if (
            type(row.get("source_bars")) is not int
            or type(row.get("expected_source_bars")) is not int
            or row["source_bars"] != expected_source_count
            or row["expected_source_bars"] != expected_source_count
        ):
            raise ValueError("Source-bar completeness mismatch")
        unit = row.get("volume_unit")
        if not isinstance(unit, str) or not unit.strip():
            raise ValueError("Missing volume-unit identity")
        if approved_volume_unit is None:
            approved_volume_unit = unit
        elif unit != approved_volume_unit:
            raise ValueError("Inconsistent volume-unit identity")

        prices: dict[str, float] = {}
        for key in ("open", "high", "low", "close", "volume"):
            value = row.get(key)
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError("Nonfinite or invalid OHLCV")
            prices[key] = float(value)
        if (
            min(prices["open"], prices["low"], prices["close"]) <= 0
            or prices["high"] < max(prices["open"], prices["close"])
            or prices["low"] > min(prices["open"], prices["close"])
            or prices["volume"] < 0
        ):
            raise ValueError("Invalid OHLCV bounds")
        closes.append(prices["close"])
        volumes.append(prices["volume"])

    returns = [math.log(closes[i]) - math.log(closes[i - 1]) for i in range(1, LOOKBACK_BARS)]
    weighted_reversals: list[float] = []
    weights: list[float] = []
    # i=2 needs adjacent returns ending at i-1 and i; last ends at i=8.
    for i in range(2, LOOKBACK_BARS):
        weight = min(volumes[i], volumes[i - 1])
        weights.append(weight)
        weighted_reversals.append(weight if returns[i - 1] * returns[i - 2] < 0 else 0.0)
    if len(weights) != REVERSAL_COMPARISONS:
        raise RuntimeError("Reversal feature window unexpectedly changed")
    denominator = math.fsum(weights)
    if not math.isfinite(denominator) or denominator <= 0:
        raise ValueError("Zero or nonfinite reversal-share denominator")
    numerator = math.fsum(weighted_reversals)
    result = numerator / denominator
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise ValueError("Reversal share is outside its mathematical domain")
    return result
