"""User-defined research: exact UTC calendar-to-calendar BTC price ratios.

An observation compares the close at two exact UTC timestamps. Missing endpoints
are never filled. These are Mojtaba's historical ratios, not AI forecasts or forecast odds.
"""

from calendar import monthrange
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal


Unit = Literal["hour", "day", "week", "month", "year"]


@dataclass(frozen=True)
class PricePoint:
    source: str
    time: datetime
    close: Decimal


@dataclass(frozen=True)
class PriceRatio:
    source: str
    period: str
    start: datetime
    end: datetime
    start_price: Decimal
    end_price: Decimal
    ratio: Decimal
    percent_change: Decimal


PERIODS: tuple[tuple[str, Unit, int], ...] = (
    ("1h", "hour", 1),
    ("1d", "day", 1),
    ("1w", "week", 1),
    ("1mo", "month", 1),
    ("3mo", "month", 3),
    ("6mo", "month", 6),
    ("1y", "year", 1),
    ("2y", "year", 2),
    ("3y", "year", 3),
    ("4y", "year", 4),
    ("5y", "year", 5),
    ("6y", "year", 6),
    ("7y", "year", 7),
    ("8y", "year", 8),
)


def advance_calendar(start: datetime, unit: Unit, count: int) -> datetime:
    """Advance a UTC timestamp; month/year endpoints respect leap years."""
    if count <= 0:
        raise ValueError("count must be positive")
    if unit == "hour":
        return start + timedelta(hours=count)
    if unit == "day":
        return start + timedelta(days=count)
    if unit == "week":
        return start + timedelta(weeks=count)
    if unit not in ("month", "year"):
        raise ValueError("Unsupported unit")
    months = count * (12 if unit == "year" else 1)
    month_index = start.year * 12 + start.month - 1 + months
    year, zero_month = divmod(month_index, 12)
    month = zero_month + 1
    return start.replace(year=year, month=month, day=min(start.day, monthrange(year, month)[1]))


def _aligned(time: datetime, unit: Unit, count: int) -> bool:
    if time.minute or time.second or time.microsecond:
        return False
    if unit == "hour":
        return True
    if time.hour:
        return False
    if unit == "day":
        return True
    if unit == "week":
        return time.weekday() == 0
    if unit == "month":
        return time.day == 1 and (time.month - 1) % count == 0
    return time.day == 1 and time.month == 1 and (time.year - 1) % count == 0


def calculate_calendar_ratios(
    points: tuple[PricePoint, ...],
    *,
    as_of: datetime,
    periods: tuple[tuple[str, Unit, int], ...] = PERIODS,
) -> tuple[PriceRatio, ...]:
    """Compare consecutive aligned calendar periods using exact observed endpoints.

    The close stamped at a boundary must be observable by as_of. For hourly
    candles, pass the *completed candle's closing timestamp*, not its open.
    A source and timestamp uniquely identify one immutable observed price.
    """
    if as_of.tzinfo is None or as_of.utcoffset() != timedelta(0):
        raise ValueError("as_of must be UTC-aware")
    by_source: dict[str, dict[datetime, Decimal]] = {}
    for point in points:
        t = point.time
        if t.tzinfo is None or t.utcoffset() != timedelta(0):
            raise ValueError("Price timestamp must be UTC-aware")
        if not point.source or not point.close.is_finite() or point.close <= 0:
            raise ValueError("Invalid source or price")
        if t > as_of:
            continue
        history = by_source.setdefault(point.source, {})
        if t in history and history[t] != point.close:
            raise ValueError("Conflicting price for source and timestamp")
        history[t] = point.close
    output: list[PriceRatio] = []
    for source, history in sorted(by_source.items()):
        for label, unit, count in periods:
            if not label or count <= 0 or unit not in ("hour", "day", "week", "month", "year"):
                raise ValueError("Invalid period")
            for start in sorted(history):
                if not _aligned(start, unit, count):
                    continue
                end = advance_calendar(start, unit, count)
                if end not in history:
                    continue
                first, last = history[start], history[end]
                ratio = last / first
                output.append(
                    PriceRatio(source, label, start, end, first, last, ratio, (ratio - 1) * 100)
                )
    return tuple(output)
