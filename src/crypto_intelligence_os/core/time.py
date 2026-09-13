"""Canonical time helpers.

All internal decision-sensitive timestamps use timezone-aware UTC datetimes.
"""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    """Normalize a timezone-aware datetime to UTC.

    Raises:
        ValueError: If ``value`` is naive and therefore ambiguous.
    """
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Naive datetimes are not allowed; provide an explicit timezone.")
    return value.astimezone(UTC)
