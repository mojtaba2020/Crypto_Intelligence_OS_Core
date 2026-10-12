"""Synthetic numeric-adversarial regression for FEATURE-03 close-order reversals.

This is not a model trial and does not read market data, locked outcomes or APIs.
"""

from __future__ import annotations

import math
import random

import pytest
from scripts.challenger_v3_reversal_share_preflight import (
    daily_volume_supported_reversal_share,
)

DAY = 86_400
START = 1_704_067_200  # canonical UTC day opening


def _bars(prices: list[float], volumes: list[float]) -> list[dict[str, object]]:
    assert len(prices) == len(volumes) == 9
    bars: list[dict[str, object]] = []
    for i, (price, volume) in enumerate(zip(prices, volumes, strict=True)):
        opening = START + i * DAY
        bars.append(
            {
                "timestamp": opening,
                "source_finalized_at": opening + DAY + 120,
                "source_bars": 1,
                "expected_source_bars": 1,
                "is_complete": True,
                "volume_unit": "base_asset",
                "open": price,
                "high": price * 1.02,
                "low": price * 0.98,
                "close": price,
                "volume": volume,
            }
        )
    return bars


def _evaluate(prices: list[float], volumes: list[float]) -> float:
    return daily_volume_supported_reversal_share(
        _bars(prices, volumes),
        8,
        asof_timestamp=START + 9 * DAY + 120,
        source_interval_seconds=DAY,
    )


def _comparison_oracle(prices: list[float], volumes: list[float]) -> float:
    """No subtraction, logarithms or floating-point products of price changes."""
    weighted = 0.0
    total = 0.0
    for i in range(2, 9):
        weight = min(volumes[i], volumes[i - 1])
        down_then_up = prices[i - 2] > prices[i - 1] < prices[i]
        up_then_down = prices[i - 2] < prices[i - 1] > prices[i]
        total += weight
        weighted += weight if down_then_up or up_then_down else 0.0
    return weighted / total


@pytest.mark.parametrize("base", [1e-200, 100.0, 1e200])
def test_alternating_adjacent_floats_do_not_erase_seven_real_reversals(
    base: float,
) -> None:
    higher = math.nextafter(base, math.inf)
    prices = [base, higher, base, higher, base, higher, base, higher, base]
    assert higher != base
    assert _evaluate(prices, [1.0] * 9) == 1.0


def test_identical_adjacent_closes_are_not_false_reversals() -> None:
    base = 100.0
    higher = math.nextafter(base, math.inf)
    prices = [base, higher, higher, base, base, higher, higher, base, base]
    weights = [1.0] * 9
    assert _comparison_oracle(prices, weights) == 0.0
    assert _evaluate(prices, weights) == 0.0


def test_tiny_price_changes_with_nonuniform_volume_match_comparison_oracle() -> None:
    base = 100.0
    high = math.nextafter(base, math.inf)
    low = math.nextafter(base, -math.inf)
    prices = [base, high, low, high, base, base, low, high, base]
    volumes = [1.0, 13.0, 9.0, 17.0, 3.0, 8.0, 4.0, 31.0, 2.0]
    assert _evaluate(prices, volumes) == pytest.approx(
        _comparison_oracle(prices, volumes), abs=1e-15
    )


def test_256_seeded_near_ulp_windows_against_direct_price_order_oracle() -> None:
    rng = random.Random(20261013)
    center = 100.0
    levels = [
        math.nextafter(center, -math.inf),
        center,
        math.nextafter(center, math.inf),
    ]
    for _ in range(256):
        prices = [rng.choice(levels) for _ in range(9)]
        volumes = [float(rng.randint(1, 100)) for _ in range(9)]
        expected = _comparison_oracle(prices, volumes)
        assert _evaluate(prices, volumes) == pytest.approx(expected, abs=1e-15)
