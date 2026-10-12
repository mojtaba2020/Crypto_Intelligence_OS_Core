"""Exact integer/mixed numeric preflight; synthetic inputs only, no market data."""

from __future__ import annotations

import math
from fractions import Fraction

import pytest
from scripts.challenger_v3_reversal_share_preflight import (
    daily_volume_supported_reversal_share,
)

DAY = 86_400
START = 1_704_067_200


def _bars(
    prices: list[int | float],
    volumes: list[int | float] | None = None,
) -> list[dict[str, object]]:
    if volumes is None:
        volumes = [1] * len(prices)
    assert len(prices) == len(volumes) == 9
    bars: list[dict[str, object]] = []
    for i, (price, volume) in enumerate(zip(prices, volumes, strict=True)):
        start = START + i * DAY
        bars.append(
            {
                "timestamp": start,
                "source_finalized_at": start + DAY + 120,
                "source_bars": 1,
                "expected_source_bars": 1,
                "is_complete": True,
                "volume_unit": "BTC",
                # Exact OHLC is valid and avoids a fixture-side float cast.
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": volume,
            }
        )
    return bars


def _value(bars: list[dict[str, object]]) -> float:
    return daily_volume_supported_reversal_share(
        bars, 8, asof_timestamp=START + 9 * DAY + 120, source_interval_seconds=DAY
    )


def _oracle(prices: list[int | float], volumes: list[int | float]) -> float:
    numerator = Fraction(0)
    denominator = Fraction(0)
    for i in range(2, 9):
        weight = Fraction(min(volumes[i], volumes[i - 1]))
        denominator += weight
        if prices[i - 2] > prices[i - 1] < prices[i] or prices[i - 2] < prices[i - 1] > prices[i]:
            numerator += weight
    return float(numerator / denominator)


def test_independent_codex_2_pow_53_integer_counterexample() -> None:
    a = 2**53
    b = a + 1
    assert a != b and float(a) == float(b)
    prices = [a, b, a, b, a, b, a, b, a]
    assert _value(_bars(prices)) == 1.0


def test_int_float_comparisons_do_not_silently_collapse_distinct_prices() -> None:
    a = 2**53
    b = a + 1
    prices = [float(a), b, float(a), b, float(a), b, float(a), b, float(a)]
    assert _value(_bars(prices)) == 1.0
    tied = [float(a), a, float(a), a, float(a), a, float(a), a, float(a)]
    assert _value(_bars(tied)) == 0.0


def test_huge_positive_integer_closes_are_not_cast_to_float() -> None:
    a = 2**1200
    b = a + 1
    prices = [a, b, a, b, a, b, a, b, a]
    assert _value(_bars(prices)) == 1.0


def test_large_integer_volume_weights_no_float_overflow() -> None:
    prices = [100, 101, 100, 101, 100, 101, 100, 101, 100]
    volumes = [10**400] * 9
    assert _value(_bars(prices, volumes)) == 1.0


def test_integer_ohlc_invalid_by_one_must_be_rejected() -> None:
    a = 2**53
    bars = _bars([a + 1] * 9)
    # high < close, though float(high) == float(close) at this magnitude.
    bars[4]["high"] = a
    with pytest.raises(ValueError, match="OHLCV bounds"):
        _value(bars)


def test_nonfinite_floats_and_bool_still_rejected() -> None:
    bars = _bars([2**53 + 1] * 9)
    bars[2]["volume"] = math.inf
    with pytest.raises(ValueError, match="Nonfinite"):
        _value(bars)
    bars[2]["volume"] = True
    with pytest.raises(ValueError, match="Nonfinite"):
        _value(bars)


def test_256_deterministic_large_int_and_mixed_float_windows() -> None:
    a = 2**53
    levels: list[int | float] = [a - 1, float(a), a + 1, a + 2]
    for trial in range(256):
        prices = [levels[(trial + 3 * i + i * i) % len(levels)] for i in range(9)]
        volumes = [((trial + 1) * (i + 3) % 19) + 1 for i in range(9)]
        assert _value(_bars(prices, volumes)) == pytest.approx(_oracle(prices, volumes), abs=1e-15)
