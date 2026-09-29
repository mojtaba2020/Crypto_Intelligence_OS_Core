from __future__ import annotations

import math

import pytest

pytest.importorskip("numpy")

from scripts.multitimeframe_tournament_v1 import HORIZONS, evaluate


def _candles(n: int) -> list[dict[str, float]]:
    rows = []
    for i in range(n):
        close = 100.0 * math.exp(0.001 * i + 0.02 * math.sin(i / 9))
        rows.append(
            {
                "open": close * 0.998,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": 1000.0 + 10.0 * math.cos(i / 5),
            }
        )
    return rows


def test_declared_horizons_match_contract() -> None:
    assert HORIZONS == {
        "daily": (1, 2, 3),
        "weekly": (1, 2, 3),
        "monthly": (1, 3),
    }


def test_daily_tournament_is_out_of_sample_and_reports_baseline() -> None:
    result = evaluate(_candles(520), "daily", horizon=1, min_train=80, step=10)
    assert result["samples"] >= 20
    assert result["ridge_mape"] >= 0.0
    assert result["persistence_mape"] >= 0.0
    assert 0.0 <= result["direction_accuracy"] <= 1.0


def test_insufficient_oos_origins_fail_closed() -> None:
    with pytest.raises(ValueError, match="Insufficient"):
        evaluate(_candles(400), "daily", horizon=3, min_train=20, step=100)
