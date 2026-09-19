"""Strict UTC aggregation of independently sourced hourly BTC/USD candles.

Never combine exchanges or silently fill missing hours. Only closed complete buckets
are eligible for historical analysis. Calendar periods use UTC boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal


@dataclass(frozen=True)
class HourCandle:
    source: str
    open_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


@dataclass(frozen=True)
class AggregateCandle:
    source: str
    open_time: datetime
    end_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    hours: int


def aggregate_fixed_hours(
    candles: tuple[HourCandle, ...],
    hours: Literal[2, 3, 4, 24, 48, 72, 168, 336, 504],
    *,
    as_of: datetime,
) -> tuple[AggregateCandle, ...]:
    """Aggregate only complete UTC-aligned periods; omit partial or gapped buckets.

    168/336/504-hour buckets anchor to Monday 1970-01-05 UTC. Other periods
    anchor to the Unix epoch. A source's candles are never mixed with another.
    """
    if as_of.tzinfo is None or as_of.utcoffset() != timedelta(0):
        raise ValueError("as_of must be timezone-aware UTC")
    if hours not in (2, 3, 4, 24, 48, 72, 168, 336, 504):
        raise ValueError("Unsupported aggregation period")
    epoch = datetime(1970, 1, 5, tzinfo=UTC) if hours >= 168 else datetime(1970, 1, 1, tzinfo=UTC)
    buckets: dict[tuple[str, datetime], dict[datetime, HourCandle]] = {}
    for bar in candles:
        t = bar.open_time
        if t.tzinfo is None or t.utcoffset() != timedelta(0) or t.minute or t.second or t.microsecond:
            raise ValueError("Hour candle must open on an exact UTC hour")
        if not bar.source or min(bar.open, bar.high, bar.low, bar.close) <= 0 or bar.volume < 0:
            raise ValueError("Invalid source, price or volume")
        if bar.low > min(bar.open, bar.close) or bar.high < max(bar.open, bar.close):
            raise ValueError("Invalid OHLC bounds")
        if t + timedelta(hours=1) > as_of:
            continue
        offset = int((t - epoch).total_seconds() // 3600)
        start = epoch + timedelta(hours=(offset // hours) * hours)
        key = (bar.source, start)
        group = buckets.setdefault(key, {})
        if t in group:
            if group[t] != bar:
                raise ValueError(f"Conflicting duplicate hour: {bar.source} {t.isoformat()}")
            continue
        group[t] = bar
    output = []
    for (source, start), group in sorted(buckets.items()):
        end = start + timedelta(hours=hours)
        if end > as_of or len(group) != hours:
            continue
        ordered = [group.get(start + timedelta(hours=i)) for i in range(hours)]
        if any(item is None for item in ordered):
            continue
        bars = [item for item in ordered if item is not None]
        output.append(AggregateCandle(source, start, end, bars[0].open,
                                      max(x.high for x in bars), min(x.low for x in bars),
                                      bars[-1].close, sum((x.volume for x in bars), Decimal(0)), hours))
    return tuple(output)
