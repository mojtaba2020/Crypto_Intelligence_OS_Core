"""Regression tests for the existing ridge inference equation with MOCK inputs only."""

from __future__ import annotations

import math
from datetime import UTC, datetime

import pytest
from scripts.stage6_dual_target_forecast_contract import HORIZONS
from scripts.stage6_synthetic_ridge_inference_bridge import (
    bridge_mock_ridge_to_13_horizon_contract,
)
from crypto_intelligence_os.hybrid_forecasting import _estimate

DAY = 86_400
JAN_1 = int(datetime(2026, 1, 1, tzinfo=UTC).timestamp())
JAN_2 = JAN_1 + DAY
MONDAY = int(datetime(2026, 1, 5, tzinfo=UTC).timestamp())
DEC_1 = int(datetime(2025, 12, 1, tzinfo=UTC).timestamp())


def _window(horizon: str, previous_price: float = 100.0, current: float = 110.0) -> dict:
    family, _ = HORIZONS[horizon]
    if family == "monthly":
        origin, prior = JAN_1, DEC_1
    elif family == "weekly":
        origin, prior = MONDAY, MONDAY - 7 * DAY
    elif family == "daily":
        origin, prior = JAN_2, JAN_1
    else:
        origin, prior = JAN_2, JAN_2 - 3_600
    return {
        "horizon": horizon,
        "origin_cutoff_utc": origin,
        "previous_cutoff_utc": prior,
        "previous_price_usd": previous_price,
        "origin_price_usd": current,
        "previous_observed_at_utc": prior + 10,
        "origin_observed_at_utc": origin + 10,
        "forecast_issued_at_utc": origin + 60,
        "source_market_id": "bitstamp:BTCUSD:spot",
        "feature_code_sha256": "c" * 64,
        "dataset_manifest_sha256": "d" * 64,
    }


def _windows() -> list[dict]:
    return [_window(h) for h in HORIZONS]


def _states() -> dict[str, dict]:
    return {
        h: {
            "weights": [0.0, 0.5],
            "means": [0.0],
            "scales": [1.0],
            "model_code_sha256": "e" * 64,
        }
        for h in HORIZONS
    }


def test_ridge_inference_equation_reused_unmodified_for_all_13() -> None:
    result = bridge_mock_ridge_to_13_horizon_contract(list(reversed(_windows())), _states())
    assert result["status"] == "SYNTHETIC_EXISTING_RIDGE_EQUATION_BRIDGE_ONLY"
    assert result["inference_equation"] == "crypto_intelligence_os.hybrid_forecasting._estimate"
    assert result["mock_state_horizons"] == 13
    assert result["trained_model_present"] is False
    assert result["real_data_evaluated"] is False
    assert result["scientific_authorization"] == "NO_RUN"
    assert result["stage7_freeze_authorized"] is False
    assert result["interval_80_95_calibrated"] is False
    assert result["forecast_accuracy_evaluated"] is False
    assert result["locked_oos_access"] is False
    batch = result["forecast_batch"]
    assert batch["horizon_count"] == 13
    assert [r["horizon"] for r in batch["forecasts"]] == list(HORIZONS)
    signal = _estimate((0.0, 0.5), (0.0,), (1.0,), (math.log1p(0.1),))
    for row in batch["forecasts"]:
        assert row["predicted_direction"] == "up"
        assert row["predicted_target_price_usd"] == pytest.approx(110.0 * math.exp(signal))
        assert row["scientific_authorization"] == "NO_RUN"


def test_zero_mock_weights_yield_only_flat_outputs() -> None:
    states = _states()
    for state in states.values():
        state["weights"] = [0.0, 0.0]
    result = bridge_mock_ridge_to_13_horizon_contract(_windows(), states)
    assert all(
        forecast["predicted_direction"] == "flat"
        for forecast in result["forecast_batch"]["forecasts"]
    )


def test_negative_mock_weights_produce_downward_outputs() -> None:
    states = _states()
    for state in states.values():
        state["weights"] = [-0.1, 0.0]
    result = bridge_mock_ridge_to_13_horizon_contract(_windows(), states)
    assert all(
        forecast["predicted_target_price_usd"] < 110.0
        for forecast in result["forecast_batch"]["forecasts"]
    )


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, True, "0.2", 10**400])
def test_model_weights_are_strict_bounded_numeric_mock_values(bad: object) -> None:
    states = _states()
    states["1h"]["weights"][1] = bad
    with pytest.raises(ValueError, match="coefficient"):
        bridge_mock_ridge_to_13_horizon_contract(_windows(), states)


@pytest.mark.parametrize("bad", [0.0, -1.0, math.nan, 1e-12, True])
def test_model_scale_must_be_valid_non_degenerate(bad: object) -> None:
    states = _states()
    states["3mo"]["scales"] = [bad]
    with pytest.raises(ValueError, match=r"scale|coefficient"):
        bridge_mock_ridge_to_13_horizon_contract(_windows(), states)


def test_nonfinite_ridge_signal_rejected_even_with_bounded_parameters() -> None:
    states = _states()
    states["1h"]["weights"] = [1000.0, 1000.0]
    states["1h"]["scales"] = [1e-8]
    windows = _windows()
    windows[0]["previous_price_usd"] = 1e-300
    windows[0]["origin_price_usd"] = 1.79e308
    # Large, finite signal is clipped and may yield a still-valid synthetic
    # output; the point and intervals may be unrepresentable, which must fail.
    with pytest.raises(ValueError, match=r"finite|unrepresentable"):
        bridge_mock_ridge_to_13_horizon_contract(windows, states)


def test_extra_future_price_field_and_incomplete_horizon_set_rejected() -> None:
    windows = _windows()
    windows[0]["actual_future_close_usd"] = 42.0
    with pytest.raises(ValueError, match="exact metadata-and-price schema"):
        bridge_mock_ridge_to_13_horizon_contract(windows, _states())
    with pytest.raises(ValueError, match="Exactly 13 synthetic input windows"):
        bridge_mock_ridge_to_13_horizon_contract(_windows()[:-1], _states())


def test_missing_model_state_and_wrong_model_state_shape_rejected() -> None:
    states = _states()
    del states["3mo"]
    with pytest.raises(ValueError, match="Exactly 13 declared mock ridge states"):
        bridge_mock_ridge_to_13_horizon_contract(_windows(), states)
    states = _states()
    states["1w"]["weights"] = [0.0, 0.5, 0.7]
    with pytest.raises(ValueError, match="exactly one feature"):
        bridge_mock_ridge_to_13_horizon_contract(_windows(), states)


def test_custom_state_mapping_mutation_cannot_bypass_contract() -> None:
    class StatefulModel(dict):
        def __getitem__(self, key: str) -> object:
            if key == "model_code_sha256":
                return "bad"
            return super().__getitem__(key)

    states = _states()
    states["1h"] = StatefulModel(states["1h"])
    with pytest.raises(ValueError, match="Exact mock model state"):
        bridge_mock_ridge_to_13_horizon_contract(_windows(), states)


def test_invalid_model_sha_is_not_treated_as_signed_evidence() -> None:
    states = _states()
    states["1d"]["model_code_sha256"] = "z" * 64
    with pytest.raises(ValueError, match="SHA-256"):
        bridge_mock_ridge_to_13_horizon_contract(_windows(), states)


def test_model_signal_must_not_turn_subnormal_drop_into_flat() -> None:
    states = _states()
    for state in states.values():
        state["weights"] = [-0.2, 0.0]
    windows = [_window(h, previous_price=2**-1073, current=2**-1074) for h in HORIZONS]
    with pytest.raises(ValueError, match="lost direction"):
        bridge_mock_ridge_to_13_horizon_contract(windows, states)


@pytest.mark.parametrize("horizon", list(HORIZONS))
def test_late_observation_in_each_horizon_rejected(horizon: str) -> None:
    windows = _windows()
    for w in windows:
        if w["horizon"] == horizon:
            w["origin_observed_at_utc"] = w["forecast_issued_at_utc"] + 1
    with pytest.raises(ValueError, match="later than claimed issuance"):
        bridge_mock_ridge_to_13_horizon_contract(windows, _states())


def test_no_real_data_or_model_fit_api_exposed_by_bridge() -> None:
    result = bridge_mock_ridge_to_13_horizon_contract(_windows(), _states())
    assert result["point_in_time_vintage_authenticated"] is False
    assert result["actual_issue_authenticated"] is False
    assert result["trained_model_present"] is False
