"""Leakage-safe descriptive relationships between BTC prices across calendar horizons.

Input: consecutive, completed, source-specific daily closes in UTC. All ratios are
historical descriptions, not probabilities or claims of predictive performance.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from math import log, sqrt
from statistics import mean


@dataclass(frozen=True)
class DailyClose:
    source: str
    day: datetime
    close: Decimal


@dataclass(frozen=True)
class HorizonRelationship:
    source: str
    horizon_days: int
    observations: int
    mean_ratio: float
    median_ratio: float
    mean_log_return: float
    positive_fraction: float
    lag_one_log_return_correlation: float | None
    first_day: datetime
    last_day: datetime


def _correlation(x: list[float], y: list[float]) -> float | None:
    if len(x) < 3:
        return None
    mx, my = mean(x), mean(y)
    xx = sum((v - mx) ** 2 for v in x)
    yy = sum((v - my) ** 2 for v in y)
    if xx == 0 or yy == 0:
        return None
    return sum((a - mx) * (b - my) for a, b in zip(x, y, strict=True)) / sqrt(xx * yy)


def historical_price_relationships(
    candles: tuple[DailyClose, ...],
    *,
    as_of: datetime,
    horizons: tuple[int, ...] = (1, 2, 3, 7, 14, 21, 30, 60, 90, 180, 365),
) -> tuple[HorizonRelationship, ...]:
    """Measure P(t+h)/P(t) on non-overlapping complete UTC-day windows.

    The 30/60/90/365-day horizons are fixed day counts, NOT calendar months/years.
    Require at least two completed windows; no forward fill, no cross-source joins.
    """
    if as_of.tzinfo is None or as_of.utcoffset() != timedelta(0):
        raise ValueError("as_of must be timezone-aware UTC")
    if not horizons or any(h <= 0 for h in horizons) or len(set(horizons)) != len(horizons):
        raise ValueError("Horizons must be distinct positive day counts")
    by_source: dict[str, dict[datetime, Decimal]] = {}
    for candle in candles:
        day = candle.day
        if day.tzinfo is None or day.utcoffset() != timedelta(0) or day.time() != datetime.min.time():
            raise ValueError("Daily closes must be stamped at UTC midnight")
        if not candle.source or not candle.close.is_finite() or candle.close <= 0:
            raise ValueError("Invalid source or close")
        if day + timedelta(days=1) > as_of:
            continue
        history = by_source.setdefault(candle.source, {})
        if day in history and history[day] != candle.close:
            raise ValueError("Conflicting close for same source and day")
        history[day] = candle.close
    results = []
    for source, history in sorted(by_source.items()):
        days = sorted(history)
        if not days:
            continue
        for horizon in horizons:
            ratios: list[float] = []
            log_returns: list[float] = []
            sampled_days: list[datetime] = []
            # Non-overlapping windows avoid treating overlapping outcomes as independent.
            for start in range(0, len(days) - horizon, horizon):
                first = days[start]
                expected = [first + timedelta(days=i) for i in range(horizon + 1)]
                if any(day not in history for day in expected):
                    continue
                ratio = float(history[expected[-1]] / history[first])
                ratios.append(ratio)
                log_returns.append(log(ratio))
                sampled_days.append(expected[-1])
            if len(ratios) < 2:
                continue
            ordered = sorted(ratios)
            n = len(ordered)
            median = (ordered[(n - 1) // 2] + ordered[n // 2]) / 2
            results.append(
                HorizonRelationship(
                    source=source,
                    horizon_days=horizon,
                    observations=n,
                    mean_ratio=mean(ratios),
                    median_ratio=median,
                    mean_log_return=mean(log_returns),
                    positive_fraction=sum(r > 1 for r in ratios) / n,
                    lag_one_log_return_correlation=_correlation(
                        log_returns[:-1], log_returns[1:]
                    ),
                    first_day=days[0],
                    last_day=sampled_days[-1],
                )
            )
    return tuple(results)
