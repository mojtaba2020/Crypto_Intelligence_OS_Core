from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_long_history_ohlcv.py"
SPEC = importlib.util.spec_from_file_location("validate_long_history_ohlcv", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def candle(timestamp: int) -> dict[str, float | int]:
    return {
        "timestamp": timestamp,
        "open": 100.0,
        "high": 102.0,
        "low": 99.0,
        "close": 101.0,
        "volume": 5.0,
    }


def test_accepts_contiguous_completed_hourly_candles() -> None:
    rows = [candle(3600), candle(7200), candle(10800)]
    report = MODULE.validate(rows, now_timestamp=18000)
    assert report["hourly_contiguous"] is True
    assert report["duplicate_timestamps"] == 0
    assert report["completed_candles_only"] is True


def test_rejects_duplicate_timestamp() -> None:
    with pytest.raises(ValueError, match="Duplicate timestamps"):
        MODULE.validate([candle(3600), candle(3600)], now_timestamp=18000)


def test_rejects_hourly_gap() -> None:
    with pytest.raises(ValueError, match="Non-hourly gaps"):
        MODULE.validate([candle(3600), candle(10800)], now_timestamp=18000)


def test_rejects_current_incomplete_candle() -> None:
    with pytest.raises(ValueError, match="incomplete/future"):
        MODULE.validate([candle(3600), candle(18000)], now_timestamp=18001)


def test_rejects_invalid_ohlc_ordering() -> None:
    bad = candle(3600)
    bad["high"] = 98.0
    with pytest.raises(ValueError, match="High price"):
        MODULE.validate([bad], now_timestamp=18000)
