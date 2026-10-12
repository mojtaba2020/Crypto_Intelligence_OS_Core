"""No market-data or CatBoost fitting: deterministic Wave-3 FEATURE-03 preflight."""

from __future__ import annotations

import copy
import math

import pytest
from scripts.challenger_v3_reversal_share_preflight import (
    daily_volume_supported_reversal_share,
)

START = 1_704_067_200  # 2024-01-01 00:00:00 UTC
DAY = 86_400


def _rows(
    prices: list[float] | None = None,
    *,
    interval: int = 86_400,
) -> list[dict[str, object]]:
    if prices is None:
        prices = [100, 110, 100, 120, 100, 120, 100, 120, 100, 110, 100]
    rows = []
    for i, price in enumerate(prices):
        timestamp = START + i * DAY
        rows.append(
            {
                "timestamp": timestamp,
                "source_finalized_at": timestamp + DAY + 120,
                "source_bars": DAY // interval,
                "expected_source_bars": DAY // interval,
                "is_complete": True,
                "volume_unit": "BTC",
                "open": price,
                "high": price * 1.02,
                "low": price * 0.98,
                "close": price,
                "volume": 1000.0,
            }
        )
    return rows


def _feature(rows: list[dict[str, object]], *, interval: int = DAY) -> float:
    return daily_volume_supported_reversal_share(
        rows,
        8,
        asof_timestamp=int(rows[8]["source_finalized_at"]),
        source_interval_seconds=interval,
    )


@pytest.mark.parametrize("interval", [3_600, 86_400])
def test_all_reversals_are_one(interval: int) -> None:
    assert _feature(_rows(interval=interval), interval=interval) == 1.0


def test_no_reversals_and_zero_returns_are_zero() -> None:
    assert _feature(_rows([100 + i for i in range(9)])) == 0.0
    assert _feature(_rows([100] * 9)) == 0.0


def test_known_five_of_seven_reversals() -> None:
    rows = _rows([100, 110, 99, 108, 100, 100, 99, 102, 101])
    assert _feature(rows) == pytest.approx(5 / 7)


def test_future_mutations_are_ignored_even_at_next_bar() -> None:
    rows = _rows()
    before = _feature(rows)
    for row in rows[9:]:
        for key in ("open", "high", "low", "close", "volume"):
            row[key] = float(row[key]) * 9
        row["is_complete"] = False
        row["timestamp"] = -123
    assert _feature(rows) == before


def test_scale_all_volumes_by_same_positive_factor_is_invariant() -> None:
    rows = _rows([100, 110, 99, 108, 100, 100, 99, 102, 101])
    before = _feature(rows)
    for row in rows[:9]:
        row["volume"] = float(row["volume"]) * 7.5
    assert _feature(rows) == pytest.approx(before)


def test_does_not_mutate_input() -> None:
    rows = _rows()
    original = copy.deepcopy(rows)
    assert math.isfinite(_feature(rows))
    assert rows == original


def test_bar_close_and_publication_delay_are_required() -> None:
    rows = _rows()
    original = int(rows[8]["source_finalized_at"])
    for not_yet_available in (int(rows[8]["timestamp"]), original - 1):
        with pytest.raises(ValueError, match="finalized/available"):
            daily_volume_supported_reversal_share(
                rows, 8, asof_timestamp=not_yet_available, source_interval_seconds=DAY
            )
    rows[8]["source_finalized_at"] = int(rows[8]["timestamp"]) + DAY - 1
    with pytest.raises(ValueError, match="finalized/available"):
        _feature(rows)


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("timestamp", START + 4 * DAY, "Noncanonical"),
        ("timestamp", START + 5 * DAY + 1, "Noncanonical"),
        ("timestamp", START + 6 * DAY, "Noncanonical"),
        ("source_bars", 0, "Source-bar"),
        ("expected_source_bars", 0, "Source-bar"),
        ("is_complete", False, "Incomplete"),
        ("volume_unit", "USD", "Inconsistent"),
        ("close", 0.0, "OHLCV"),
        ("close", float("nan"), "Nonfinite"),
        ("volume", -1.0, "OHLCV"),
        ("volume", float("inf"), "Nonfinite"),
        ("high", 1.0, "OHLCV"),
        ("low", -1.0, "OHLCV"),
    ],
)
def test_corrupt_required_bar_fails_closed(field: str, value: object, reason: str) -> None:
    rows = _rows()
    rows[5][field] = value
    with pytest.raises(ValueError, match=reason):
        _feature(rows)


def test_missing_history_and_missing_fields_fail_closed() -> None:
    rows = _rows()
    with pytest.raises(ValueError, match="nine"):
        daily_volume_supported_reversal_share(
            rows, 7, asof_timestamp=START + 8 * DAY + 120, source_interval_seconds=DAY
        )
    del rows[5]["source_finalized_at"]
    with pytest.raises(ValueError, match="finalized/available"):
        _feature(rows)


def test_all_zero_volume_denominator_is_rejected() -> None:
    rows = _rows()
    for row in rows:
        row["volume"] = 0.0
    with pytest.raises(ValueError, match="denominator"):
        _feature(rows)


@pytest.mark.parametrize("bad_interval", [0, 1, 86_401, True, 1800])
def test_only_declared_source_intervals(bad_interval: object) -> None:
    rows = _rows()
    with pytest.raises(ValueError, match="audited hourly/daily"):
        daily_volume_supported_reversal_share(
            rows,
            8,
            asof_timestamp=int(rows[8]["source_finalized_at"]),
            source_interval_seconds=bad_interval,
        )


def test_missing_gap_does_not_get_interpolated() -> None:
    rows = _rows()
    rows.pop(5)
    with pytest.raises(ValueError, match="Noncanonical"):
        daily_volume_supported_reversal_share(
            rows,
            8,
            asof_timestamp=START + 11 * DAY,
            source_interval_seconds=DAY,
        )
