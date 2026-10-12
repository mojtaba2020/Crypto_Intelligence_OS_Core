"""Additional synthetic adversarial checks for unintegrated Wave-3 FEATURE-03.

These tests neither observe actual market data nor fit an estimator.
"""

from __future__ import annotations

import math

import pytest
from scripts.challenger_v3_reversal_share_preflight import (
    daily_volume_supported_reversal_share,
)

DAY = 86_400
START = 1_704_067_200  # 2024-01-01 UTC
CLOSES = [100.0, 107.0, 101.0, 109.0, 96.0, 96.0, 112.0, 100.0, 115.0, 103.0, 109.0]
VOLUMES = [1.0, 3.0, 7.0, 11.0, 2.0, 8.0, 5.0, 13.0, 9.0, 4.0, 6.0]


def _fixture() -> list[dict[str, object]]:
    bars: list[dict[str, object]] = []
    for i, (close, volume) in enumerate(zip(CLOSES, VOLUMES, strict=True)):
        opening = START + i * DAY
        bars.append(
            {
                "timestamp": opening,
                "source_finalized_at": opening + DAY + 120,
                "source_bars": 1,
                "expected_source_bars": 1,
                "is_complete": True,
                "volume_unit": "base_asset",
                "open": close,
                "high": close * 1.02,
                "low": close * 0.98,
                "close": close,
                "volume": volume,
            }
        )
    return bars


def _value(bars: list[dict[str, object]], origin: int) -> float:
    return daily_volume_supported_reversal_share(
        bars,
        origin,
        asof_timestamp=START + (origin + 1) * DAY + 120,
        source_interval_seconds=DAY,
    )


@pytest.mark.parametrize("origin", [8, 9, 10])
def test_sliding_window_matches_independent_formula_oracle(origin: int) -> None:
    bars = _fixture()
    returns = [math.log(CLOSES[j] / CLOSES[j - 1]) for j in range(1, len(CLOSES))]
    weights = [min(VOLUMES[i], VOLUMES[i - 1]) for i in range(origin - 6, origin + 1)]
    indicators = [float(returns[i - 1] * returns[i - 2] < 0) for i in range(origin - 6, origin + 1)]
    expected = sum(w * sign for w, sign in zip(weights, indicators, strict=True)) / sum(weights)
    assert _value(bars, origin) == pytest.approx(expected, abs=1e-14)


def test_origin_close_is_used_not_treated_as_future() -> None:
    bars = _fixture()
    initial = _value(bars, 8)
    # A zero return at the current closed bar removes its last reversal.
    bars[8]["close"] = bars[7]["close"]
    bars[8]["low"] = float(bars[8]["close"]) * 0.98
    assert _value(bars, 8) < initial


def test_first_required_close_affects_oldest_adjacent_return() -> None:
    bars = _fixture()
    initial = _value(bars, 8)
    # Change the first return from up to down while keeping candle valid.
    bars[0]["close"] = 120.0
    bars[0]["high"] = 125.0
    assert _value(bars, 8) != pytest.approx(initial)


def test_canonical_bar_close_is_allowed_only_if_source_finalized() -> None:
    bars = _fixture()
    bars[8]["source_finalized_at"] = START + 9 * DAY
    assert math.isfinite(
        daily_volume_supported_reversal_share(
            bars, 8, asof_timestamp=START + 9 * DAY, source_interval_seconds=DAY
        )
    )
    bars[8]["source_finalized_at"] += 1
    with pytest.raises(ValueError, match="finalized/available"):
        daily_volume_supported_reversal_share(
            bars, 8, asof_timestamp=START + 9 * DAY, source_interval_seconds=DAY
        )


def test_an_earlier_bar_with_late_publication_blocks_forecast() -> None:
    bars = _fixture()
    bars[4]["source_finalized_at"] = START + 10 * DAY
    with pytest.raises(ValueError, match="finalized/available"):
        _value(bars, 8)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("timestamp", True, "Noncanonical"),
        ("source_finalized_at", True, "finalized/available"),
        ("volume", True, "Nonfinite"),
        ("source_bars", True, "Source-bar"),
        ("expected_source_bars", 1.5, "Source-bar"),
        ("volume_unit", "", "Missing volume-unit"),
        ("open", -1.0, "OHLCV"),
    ],
)
def test_rejects_ambiguous_boolean_and_invalid_metadata(
    field: str, value: object, message: str
) -> None:
    bars = _fixture()
    bars[4][field] = value
    with pytest.raises(ValueError, match=message):
        _value(bars, 8)


def test_history_window_does_not_require_unrelated_earlier_bars() -> None:
    bars = _fixture()
    bars[0]["is_complete"] = False
    # Origin=9 uses only bars [1..9]; unrelated, earlier bar must not poison it.
    assert math.isfinite(_value(bars, 9))
