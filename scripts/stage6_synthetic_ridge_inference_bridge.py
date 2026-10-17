"""Synthetic-only inference bridge to the existing hybrid ridge estimator.

Reuses the production research equation crypto_intelligence_os.hybrid_forecasting._estimate
with caller-provided MOCK frozen coefficients. It NEVER fits a model, reads a
dataset, contacts a provider or uses outcomes. Not a 13-horizon trained engine.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from scripts.stage6_dual_target_forecast_contract import (
    HORIZONS,
    _digest,
    validate_full_13_horizon_batch,
)
from scripts.stage6_synthetic_baseline_adapters import (
    _illustrative_intervals,
    _inspect_synthetic_window,
)

from crypto_intelligence_os.hybrid_forecasting import _estimate

STATE_KEYS = frozenset({"weights", "means", "scales", "model_code_sha256"})
MAX_COEFFICIENT = 1_000.0


def _finite_coefficient(value: object, label: str) -> float:
    if type(value) not in (int, float):
        raise ValueError(f"{label} must be a finite bounded real coefficient")
    try:
        number = float(value)
    except OverflowError as exc:
        raise ValueError(f"{label} exceeds finite coefficient range") from exc
    if not math.isfinite(number) or abs(number) > MAX_COEFFICIENT:
        raise ValueError(f"{label} must be a finite bounded real coefficient")
    return number


def _validated_mock_state(
    state: Mapping[str, object],
) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...], str]:
    if type(state) is not dict or set(state) != STATE_KEYS:
        raise ValueError("Exact mock model state required; no model objects or fitted labels")
    weights = state["weights"]
    means = state["means"]
    scales = state["scales"]
    if (
        type(weights) is not list
        or len(weights) != 2
        or type(means) is not list
        or len(means) != 1
        or type(scales) is not list
        or len(scales) != 1
    ):
        raise ValueError("Mock ridge expects exactly one feature and two weights")
    w = tuple(_finite_coefficient(x, "model weight") for x in weights)
    m = (_finite_coefficient(means[0], "feature mean"),)
    s = (_finite_coefficient(scales[0], "feature scale"),)
    if s[0] < 1e-8:
        raise ValueError("Mock ridge scale must be positive and nondegenerate")
    digest = _digest(state["model_code_sha256"], "model code digest")
    return w, m, s, digest


def _synthetic_log_return(previous: float, current: float) -> float:
    """Numerically stable one-bar feature, with no future prices involved."""
    if 0.5 * previous <= current <= 2.0 * previous:
        value = math.log1p((current - previous) / previous)
    else:
        value = math.log(current) - math.log(previous)
    if not math.isfinite(value) or (previous != current and value == 0.0):
        raise ValueError("Synthetic log feature collapsed or overflowed")
    return value


def bridge_mock_ridge_to_13_horizon_contract(
    windows: list[dict[str, object]],
    mock_states_by_horizon: Mapping[str, object],
) -> dict[str, object]:
    """Exercise the REAL _estimate equation on 13 entirely synthetic mock states.

    This is an interface/compatibility test, never real historical fitting,
    predictive evidence, trained ridge weights or a publication receipt.
    """
    if type(windows) is not list or len(windows) != len(HORIZONS):
        raise ValueError("Exactly 13 synthetic input windows required")
    if type(mock_states_by_horizon) is not dict or set(mock_states_by_horizon) != set(HORIZONS):
        raise ValueError("Exactly 13 declared mock ridge states required")

    inspected = [_inspect_synthetic_window(window) for window in windows]
    if len({row["horizon"] for row in inspected}) != len(HORIZONS):
        raise ValueError("Missing or duplicate synthetic horizon")
    states = {
        horizon: _validated_mock_state(mock_states_by_horizon[horizon]) for horizon in HORIZONS
    }
    records: list[dict[str, object]] = []
    for row in inspected:
        horizon = str(row["horizon"])
        previous = float(row["previous_price_usd"])
        origin_price = float(row["origin_price_usd"])
        feature = _synthetic_log_return(previous, origin_price)
        weights, means, scales, model_digest = states[horizon]

        # The existing _estimate arithmetic multiplies the slope by the
        # centered feature BEFORE dividing by the scale. Refuse inputs whose
        # nonzero contribution is rounded to zero at either operation.
        centered = feature - means[0]
        raw_term = weights[1] * centered
        if weights[1] != 0.0 and centered != 0.0 and raw_term == 0.0:
            raise ValueError("Mock ridge term lost to floating underflow")
        scaled_term = raw_term / scales[0]
        if raw_term != 0.0 and scaled_term == 0.0:
            raise ValueError("Mock ridge scale erased a nonzero contribution")
        if scaled_term != 0.0 and weights[0] + scaled_term == weights[0]:
            raise ValueError("Mock ridge contribution lost to floating cancellation")

        # This calls the EXISTING project's unmodified ridge inference
        # arithmetic; all coefficients and features are mock synthetic inputs.
        predicted_log_return = _estimate(weights, means, scales, (feature,))
        if not math.isfinite(predicted_log_return):
            raise ValueError("Mock ridge inference returned a nonfinite log return")
        point = origin_price * math.exp(max(-0.20, min(0.20, predicted_log_return)))
        if not math.isfinite(point) or point <= 0:
            raise ValueError("Mock ridge produced an unrepresentable positive price")
        if predicted_log_return != 0.0 and point == origin_price:
            raise ValueError("Mock ridge signal lost direction to float underflow")
        low80, high80, low95, high95 = _illustrative_intervals(point)
        records.append(
            {
                "horizon": horizon,
                "origin_cutoff_utc": row["origin_cutoff_utc"],
                "forecast_issued_at_utc": row["forecast_issued_at_utc"],
                "target_end_utc": row["target_end_utc"],
                "source_market_id": row["source_market_id"],
                "origin_price_usd": origin_price,
                "predicted_target_price_usd": point,
                "predicted_direction": (
                    "up" if point > origin_price else "down" if point < origin_price else "flat"
                ),
                "interval_80_low_usd": low80,
                "interval_80_high_usd": high80,
                "interval_95_low_usd": low95,
                "interval_95_high_usd": high95,
                "model_code_sha256": model_digest,
                "feature_code_sha256": row["feature_code_sha256"],
                "dataset_manifest_sha256": row["dataset_manifest_sha256"],
            }
        )
    result = validate_full_13_horizon_batch(records)
    return {
        "status": "SYNTHETIC_EXISTING_RIDGE_EQUATION_BRIDGE_ONLY",
        "mock_state_horizons": len(states),
        "inference_equation": "crypto_intelligence_os.hybrid_forecasting._estimate",
        "forecast_batch": result,
        "scientific_authorization": "NO_RUN",
        "stage7_freeze_authorized": False,
        "real_data_evaluated": False,
        "trained_model_present": False,
        "point_in_time_vintage_authenticated": False,
        "actual_issue_authenticated": False,
        "interval_80_95_calibrated": False,
        "forecast_accuracy_evaluated": False,
        "locked_oos_access": False,
    }
