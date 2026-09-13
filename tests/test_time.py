from datetime import UTC, datetime, timedelta, timezone

import pytest

from crypto_intelligence_os.core.time import ensure_utc, utc_now


def test_utc_now_is_timezone_aware_utc() -> None:
    value = utc_now()
    assert value.tzinfo is UTC
    assert value.utcoffset() == timedelta(0)


def test_ensure_utc_converts_timezone_aware_value() -> None:
    source = datetime(2026, 9, 13, 8, 0, tzinfo=timezone(timedelta(hours=3, minutes=30)))
    converted = ensure_utc(source)
    assert converted == datetime(2026, 9, 13, 4, 30, tzinfo=UTC)


def test_ensure_utc_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="Naive datetimes"):
        ensure_utc(datetime(2026, 9, 13, 8, 0))
