from __future__ import annotations

from datetime import UTC, datetime

import pytest
from scripts.resample_multitimeframe_ohlcv import aggregate, audit_source_rows, source_data_identity


def _ts(year: int, month: int, day: int, hour: int = 0) -> int:
    return int(datetime(year, month, day, hour, tzinfo=UTC).timestamp())


def _row(ts: int, price: float, volume: float = 1.0) -> dict[str, float]:
    return {
        "timestamp": float(ts),
        "open": price,
        "high": price + 2.0,
        "low": price - 2.0,
        "close": price + 1.0,
        "volume": volume,
    }


def test_daily_aggregation_uses_canonical_utc_midnight() -> None:
    start = _ts(2026, 9, 28)
    rows = [_row(start + hour * 3600, 100.0 + hour, 2.0) for hour in range(48)]
    daily = aggregate(rows, "1d")
    assert [bar["timestamp"] for bar in daily] == [start, start + 86400]
    assert daily[0]["open"] == 100.0
    assert daily[0]["close"] == 124.0
    assert daily[0]["source_bars"] == 24


def test_weekly_bucket_opens_monday_utc() -> None:
    sunday = _ts(2026, 9, 27, 23)
    monday = _ts(2026, 9, 28)
    weekly = aggregate([_row(sunday, 100.0), _row(monday, 110.0)], "1w")
    assert len(weekly) == 2
    assert weekly[0]["timestamp"] == _ts(2026, 9, 21)
    assert weekly[1]["timestamp"] == monday


def test_calendar_month_boundary_uses_first_day_utc() -> None:
    jan_last = _ts(2026, 1, 31, 23)
    feb_first = _ts(2026, 2, 1)
    monthly = aggregate([_row(jan_last, 100.0), _row(feb_first, 110.0)], "1mo")
    assert [bar["timestamp"] for bar in monthly] == [_ts(2026, 1, 1), feb_first]


def test_as_of_drops_partial_final_target_bucket() -> None:
    day1 = _ts(2026, 9, 28)
    rows = [_row(day1 + hour * 3600, 100.0 + hour) for hour in range(30)]
    as_of = _ts(2026, 9, 29, 6)
    daily = aggregate(rows, "1d", as_of_timestamp=as_of)
    assert len(daily) == 1
    assert daily[0]["timestamp"] == day1
    assert daily[0]["source_bars"] == 24


def test_as_of_excludes_source_bar_that_is_not_closed_yet() -> None:
    day = _ts(2026, 9, 28)
    rows = [_row(day + hour * 3600, 100.0 + hour) for hour in range(24)]
    daily = aggregate(rows, "1d", as_of_timestamp=day + 23 * 3600 + 1800)
    assert daily == []


def test_resampling_is_chronological_even_if_input_is_reversed() -> None:
    start = _ts(2026, 9, 28)
    rows = [_row(start + hour * 3600, 100.0 + hour) for hour in range(48)]
    assert aggregate(rows, "1d") == aggregate(list(reversed(rows)), "1d")


def test_unknown_timeframe_fails_closed() -> None:
    try:
        aggregate([_row(0, 100.0)], "4h")
    except ValueError as exc:
        assert "Unsupported timeframe" in str(exc)
    else:
        raise AssertionError("Unsupported timeframe must fail closed")


def test_duplicate_source_timestamp_fails_closed() -> None:
    ts = _ts(2026, 9, 28)
    with pytest.raises(ValueError, match="Duplicate"):
        aggregate([_row(ts, 100.0), _row(ts, 101.0)], "1d")


def test_invalid_ohlc_fails_closed() -> None:
    row = _row(_ts(2026, 9, 28), 100.0)
    row["high"] = 90.0
    with pytest.raises(ValueError, match="High is inconsistent"):
        aggregate([row], "1d")


def test_strict_daily_bucket_rejects_missing_hour() -> None:
    start = _ts(2026, 9, 28)
    rows = [_row(start + hour * 3600, 100.0 + hour) for hour in range(24) if hour != 7]
    with pytest.raises(ValueError, match="Incomplete 1d bucket"):
        aggregate(rows, "1d", require_complete_buckets=True)


def test_strict_daily_bucket_accepts_exact_complete_source_grid() -> None:
    start = _ts(2026, 9, 28)
    rows = [_row(start + hour * 3600, 100.0 + hour) for hour in range(24)]
    daily = aggregate(rows, "1d", require_complete_buckets=True)
    assert daily[0]["source_bars"] == 24


def test_source_audit_and_identity_are_order_independent() -> None:
    start = _ts(2026, 9, 28)
    rows = [_row(start + hour * 3600, 100.0 + hour) for hour in range(3)]
    audit = audit_source_rows(rows)
    assert audit["continuous"] is True
    assert audit["gap_count"] == 0
    assert source_data_identity(rows) == source_data_identity(list(reversed(rows)))


def test_aggregate_preserves_incomplete_bucket_with_validity_metadata() -> None:
    start = _ts(2026, 9, 28)
    rows = [_row(start + hour * 3600, 100.0 + hour) for hour in range(48)]
    rows.pop(5)
    result = aggregate(rows, "1d")
    assert len(result) == 2
    assert result[0]["is_complete"] is False
    assert result[0]["source_bars"] == 23
    assert result[0]["expected_source_bars"] == 24
    assert result[1]["is_complete"] is True


def test_aggregate_preserves_fully_missing_calendar_bucket_as_invalid_marker() -> None:
    start = _ts(2026, 9, 27)
    rows = [_row(start + hour * 3600, 100.0 + hour) for hour in range(72)]
    rows = [row for row in rows if not (start + 86_400 <= int(row["timestamp"]) < start + 172_800)]
    result = aggregate(rows, "1d")
    assert len(result) == 3
    assert result[0]["is_complete"] is True
    assert result[1]["timestamp"] == start + 86_400
    assert result[1]["source_bars"] == 0
    assert result[1]["is_complete"] is False
    assert result[2]["is_complete"] is True
