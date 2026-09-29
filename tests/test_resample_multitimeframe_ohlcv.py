from __future__ import annotations

from scripts.resample_multitimeframe_ohlcv import aggregate


def _row(ts: int, price: float, volume: float = 1.0) -> dict[str, float]:
    return {
        "timestamp": float(ts),
        "open": price,
        "high": price + 2.0,
        "low": price - 2.0,
        "close": price + 1.0,
        "volume": volume,
    }


def test_daily_aggregation_preserves_ohlcv_semantics() -> None:
    rows = [_row(hour * 3600, 100.0 + hour, 2.0) for hour in range(48)]
    daily = aggregate(rows, "1d")
    assert len(daily) == 2
    assert daily[0]["open"] == 100.0
    assert daily[0]["close"] == 124.0
    assert daily[0]["high"] == 125.0
    assert daily[0]["low"] == 98.0
    assert daily[0]["volume"] == 48.0
    assert daily[0]["source_bars"] == 24


def test_resampling_is_chronological_even_if_input_is_reversed() -> None:
    rows = [_row(hour * 3600, 100.0 + hour) for hour in range(48)]
    assert aggregate(rows, "1d") == aggregate(list(reversed(rows)), "1d")


def test_month_boundary_creates_distinct_bars() -> None:
    jan_31_23 = 2678399
    feb_1_00 = 2678400
    monthly = aggregate([_row(jan_31_23, 100.0), _row(feb_1_00, 110.0)], "1mo")
    assert len(monthly) == 2


def test_unknown_timeframe_fails_closed() -> None:
    try:
        aggregate([_row(0, 100.0)], "4h")
    except ValueError as exc:
        assert "Unsupported timeframe" in str(exc)
    else:
        raise AssertionError("Unsupported timeframe must fail closed")
