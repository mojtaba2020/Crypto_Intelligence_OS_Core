from __future__ import annotations

import math

import pytest

pytest.importorskip("numpy")

from scripts.multitimeframe_features_v3 import feature_vector
from scripts.multitimeframe_tournament_v1 import HORIZONS, _known_training_origins, evaluate


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
    result = evaluate(_candles(700), "daily", horizon=1, min_train=80, step=10)
    assert result["samples"] >= 20
    assert result["candidates"]["ridge"]["mape"] >= 0.0
    assert set(result["candidates"]) == {"ridge", "extra_trees", "boosting"}
    assert result["persistence_mape"] >= 0.0
    for candidate in result["candidates"].values():
        assert 0.0 <= candidate["direction_accuracy"] <= 1.0


def test_insufficient_oos_origins_fail_closed() -> None:
    with pytest.raises(ValueError, match="Insufficient"):
        evaluate(_candles(400), "daily", horizon=3, min_train=20, step=100)


def test_training_labels_are_known_at_forecast_origin() -> None:
    for horizon in (1, 2, 3):
        origins = _known_training_origins(10, 25, horizon)
        assert origins
        assert max(i + horizon for i in origins) <= 25
        assert all(i < 25 for i in origins)


def test_future_bars_do_not_change_prediction_inputs() -> None:
    candles = _candles(700)
    origin = 500
    horizon = 3
    train = _known_training_origins(365, origin, horizon)
    baseline_x = [tuple(feature_vector(candles, i, "daily")) for i in train]
    baseline_y = [math.log(candles[i + horizon]["close"] / candles[i]["close"]) for i in train]
    mutated = [dict(row) for row in candles]
    for i in range(origin + 1, len(mutated)):
        mutated[i]["close"] *= 50.0
        mutated[i]["high"] *= 50.0
        mutated[i]["low"] *= 50.0
        mutated[i]["open"] *= 50.0
        mutated[i]["volume"] *= 50.0
    mutated_x = [tuple(feature_vector(mutated, i, "daily")) for i in train]
    mutated_y = [math.log(mutated[i + horizon]["close"] / mutated[i]["close"]) for i in train]
    assert mutated_x == baseline_x
    assert mutated_y == baseline_y
