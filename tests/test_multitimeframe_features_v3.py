from __future__ import annotations

import math

import pytest
from scripts.multitimeframe_features_v3 import (
    feature_names,
    feature_vector,
    has_valid_feature_history,
    has_valid_forecast_target,
    is_temporally_valid_sample,
)


def _candles(n: int) -> list[dict[str, float]]:
    rows = []
    for i in range(n):
        close = 100.0 * math.exp(0.001 * i + 0.01 * math.sin(i / 7))
        rows.append(
            {
                "open": close * 0.999,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": 1000.0 + i,
            }
        )
    return rows


@pytest.mark.parametrize(
    ("family", "origin"),
    [("daily", 365), ("weekly", 52), ("monthly", 36)],
)
def test_feature_vector_is_finite_and_matches_schema(family: str, origin: int) -> None:
    values = feature_vector(_candles(origin + 10), origin, family)
    assert len(values) == len(feature_names(family))
    assert all(math.isfinite(value) for value in values)


def test_feature_vector_is_point_in_time_safe() -> None:
    candles = _candles(400)
    before = feature_vector(candles, 365, "daily")
    for row in candles[366:]:
        row["close"] *= 100.0
        row["high"] *= 100.0
        row["low"] *= 100.0
        row["open"] *= 100.0
        row["volume"] *= 100.0
    after = feature_vector(candles, 365, "daily")
    assert before == after


def test_unknown_family_fails_closed() -> None:
    with pytest.raises(KeyError):
        feature_names("hourly")


def test_gap_safe_sample_rejects_missing_daily_period() -> None:
    candles = _candles(370)
    for i, row in enumerate(candles):
        row["timestamp"] = float(i * 86_400)
    assert is_temporally_valid_sample(candles, "daily", 365, 1)
    candles[200]["timestamp"] += 86_400
    assert not is_temporally_valid_sample(candles, "daily", 365, 1)


def test_gap_safe_sample_rejects_target_crossing_gap() -> None:
    candles = _candles(370)
    for i, row in enumerate(candles):
        row["timestamp"] = float(i * 86_400)
    candles[366]["timestamp"] += 86_400
    assert not is_temporally_valid_sample(candles, "daily", 365, 1)


def test_feature_and_target_continuity_are_checked_independently() -> None:
    candles = _candles(800)
    for i, row in enumerate(candles):
        row["timestamp"] = float(i * 86_400)
    # An old unrelated gap must not poison a later otherwise-valid sample.
    candles[10]["timestamp"] += 86_400
    assert has_valid_feature_history(candles, "daily", 700)
    assert has_valid_forecast_target(candles, "daily", 700, 3)
    assert is_temporally_valid_sample(candles, "daily", 700, 3)


def test_feature_history_gap_does_not_invalidate_unrelated_target_logic() -> None:
    candles = _candles(800)
    for i, row in enumerate(candles):
        row["timestamp"] = float(i * 86_400)
    candles[500]["timestamp"] += 86_400
    assert not has_valid_feature_history(candles, "daily", 700)
    assert has_valid_forecast_target(candles, "daily", 700, 3)
    assert not is_temporally_valid_sample(candles, "daily", 700, 3)


def test_incomplete_bucket_mask_invalidates_only_windows_that_touch_it() -> None:
    candles = _candles(800)
    for i, row in enumerate(candles):
        row["timestamp"] = float(i * 86_400)
        row["is_complete"] = True
    candles[100]["is_complete"] = False
    assert is_temporally_valid_sample(candles, "daily", 700, 3)
    candles[500]["is_complete"] = False
    assert not is_temporally_valid_sample(candles, "daily", 700, 3)


@pytest.mark.parametrize(
    ("family", "origin"),
    [("daily", 365), ("weekly", 52), ("monthly", 36)],
)
def test_regime_features_are_declared_and_finite(family: str, origin: int) -> None:
    names = feature_names(family)
    assert any(name.startswith("trend_") for name in names)
    assert any(name.startswith("vol_ratio_") for name in names)
    values = feature_vector(_candles(origin + 10), origin, family)
    assert len(values) == len(names)
    assert all(math.isfinite(value) for value in values)


def test_regime_features_do_not_read_future_rows() -> None:
    candles = _candles(500)
    origin = 365
    before = feature_vector(candles, origin, "daily")
    for row in candles[origin + 1 :]:
        row["open"] *= 1_000.0
        row["high"] *= 1_000.0
        row["low"] *= 1_000.0
        row["close"] *= 1_000.0
        row["volume"] *= 1_000.0
    assert feature_vector(candles, origin, "daily") == before


@pytest.mark.parametrize(
    ("family", "origin"),
    [("daily", 365), ("weekly", 52), ("monthly", 36)],
)
def test_baseline_ablation_exactly_matches_legacy_feature_prefix(family: str, origin: int) -> None:
    from scripts.challenger_v3_feature_ablation import apply_mask, feature_mask

    candles = _candles(origin + 10)
    full = feature_vector(candles, origin, family)
    baseline_mask = feature_mask(family, "baseline")
    baseline = apply_mask(full, baseline_mask)

    names = feature_names(family)
    regime_prefixes = ("trend_", "vol_ratio_", "range_position_")
    legacy_indices = tuple(
        i for i, name in enumerate(names)
        if not name.startswith(regime_prefixes)
    )
    assert baseline_mask == legacy_indices
    assert baseline == [full[i] for i in legacy_indices]
    assert len(baseline) + 7 == len(full)


@pytest.mark.parametrize(
    ("family", "origin", "window"),
    [("daily", 365, 30), ("weekly", 52, 13), ("monthly", 36, 6)],
)
def test_regime_realized_vol_matches_original_trailing_semantics(
    family: str, origin: int, window: int
) -> None:
    import statistics
    from scripts.multitimeframe_features_v3 import _realized_vol

    candles = _candles(origin + 10)
    returns = [
        math.log(float(candles[i]["close"]) / float(candles[i - 1]["close"]))
        for i in range(origin - max(window, 1) + 1, origin + 1)
    ]
    assert _realized_vol(candles, origin, window) == pytest.approx(
        statistics.pstdev(returns)
    )
