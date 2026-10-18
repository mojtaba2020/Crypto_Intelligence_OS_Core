"""Synthetic multi-feature compatibility lane for the repository's hybrid Ridge equation.

Never deserializes Python objects, fits models, reads market rows or checks real
provenance. Mock 13-horizon states and feature values are supplied IN MEMORY.
The existing hybrid model trains on DAILY observations only; using its equation
here does not mean hourly/weekly/monthly Ridge checkpoints were fitted.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math

from scripts.stage6_dual_target_forecast_contract import (
    HORIZONS,
    _digest,
    _utc_timestamp,
    validate_full_13_horizon_batch,
)
from scripts.stage6_synthetic_baseline_adapters import (
    _illustrative_intervals,
    _inspect_synthetic_window,
)
from scripts.stage6_synthetic_prefit_bundle import (
    MAX_BUNDLE_BYTES,
    _canonical_bytes,
    _no_duplicate_keys,
    _reject_nonjson_number,
)
from scripts.stage6_synthetic_ridge_inference_bridge import _finite_coefficient

from crypto_intelligence_os.hybrid_forecasting import _estimate

FORMAT = "stage6-synthetic-hybrid-multifeature-v1"
MOMENTUM = (
    "log_return_7d",
    "log_return_30d",
    "log_return_90d",
    "log_return_180d",
    "log_return_365d",
)
VOLATILITY = ("realized_volatility_30d",)
EXTREMA = (
    "log_to_90d_high",
    "log_to_90d_low",
    "log_to_365d_high",
    "log_to_365d_low",
)
HALVING = ("days_since_halving_normalized", "days_since_halving_squared")
FEATURE_LAYOUTS = {
    "all": MOMENTUM + VOLATILITY + EXTREMA + HALVING,
    "no_halving": MOMENTUM + VOLATILITY + EXTREMA,
    "no_extrema": MOMENTUM + VOLATILITY + HALVING,
    "momentum_only": MOMENTUM,
}
ENVELOPE_KEYS = frozenset({"format", "classification", "real_data_authorized", "model_states"})
STATE_KEYS = frozenset(
    {
        "feature_group",
        "feature_names",
        "weights",
        "means",
        "scales",
        "blend",
        "model_code_sha256",
        "last_training_target_utc",
        "model_created_at_utc",
    }
)
ROW_KEYS = frozenset({"horizon", "feature_group", "feature_names", "values", "observed_at_utc"})


def _names(group: object, names: object) -> tuple[str, ...]:
    if type(group) is not str or group not in FEATURE_LAYOUTS:
        raise ValueError("Unsupported hybrid feature group")
    expected = FEATURE_LAYOUTS[group]
    if type(names) is not list or names != list(expected):
        raise ValueError("Feature names must exactly match production group order")
    return expected


def _mock_state(state: object) -> dict[str, object]:
    if type(state) is not dict or set(state) != STATE_KEYS:
        raise ValueError("Exact mock multi-feature state required")
    group = state["feature_group"]
    names = _names(group, state["feature_names"])
    weights, means, scales = state["weights"], state["means"], state["scales"]
    if (
        type(weights) is not list
        or len(weights) != len(names) + 1
        or type(means) is not list
        or len(means) != len(names)
        or type(scales) is not list
        or len(scales) != len(names)
    ):
        raise ValueError("Mock hybrid weight, mean and scale dimensions disagree")
    weight_values = [_finite_coefficient(value, "weight") for value in weights]
    mean_values = [_finite_coefficient(value, "mean") for value in means]
    scale_values = [_finite_coefficient(value, "scale") for value in scales]
    if any(value < 1e-8 for value in scale_values):
        raise ValueError("Mock hybrid scales must be positive and nondegenerate")
    blend = _finite_coefficient(state["blend"], "blend")
    if not 0.0 <= blend <= 1.0:
        raise ValueError("Mock hybrid blend must be between zero and one")
    last_target, _ = _utc_timestamp(state["last_training_target_utc"], "last training target")
    created, _ = _utc_timestamp(state["model_created_at_utc"], "model creation")
    if last_target > created:
        raise ValueError("Mock model creation precedes last resolved training target")
    digest = _digest(state["model_code_sha256"], "mock model code digest")
    return {
        "feature_group": group,
        "feature_names": list(names),
        "weights": weight_values,
        "means": mean_values,
        "scales": scale_values,
        "blend": blend,
        "model_code_sha256": digest,
        "last_training_target_utc": last_target,
        "model_created_at_utc": created,
    }


def inspect_synthetic_multifeature_bundle(
    payload: bytes, expected_local_sha256: str
) -> dict[str, object]:
    """Validate a bounded MOCK bundle; a matching SELF hash is not an attestation."""
    if type(payload) is not bytes or not 0 < len(payload) <= MAX_BUNDLE_BYTES:
        raise ValueError("Bounded plain MOCK bundle bytes required")
    expected = _digest(expected_local_sha256, "expected local bundle digest")
    actual = hashlib.sha256(payload).hexdigest()
    if not hmac.compare_digest(actual, expected):
        raise ValueError("Mock multi-feature bundle SHA-256 mismatch")
    try:
        document = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_no_duplicate_keys,
            parse_constant=_reject_nonjson_number,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid UTF-8 JSON bundle") from exc
    if type(document) is not dict or set(document) != ENVELOPE_KEYS:
        raise ValueError("Unknown fields in mock multi-feature envelope")
    if (
        type(document["format"]) is not str
        or document["format"] != FORMAT
        or document["classification"] != "MOCK_MULTIFEATURE_ONLY"
        or type(document["classification"]) is not str
        or document["real_data_authorized"] is not False
    ):
        raise ValueError("Mock-only format and NO_RUN required")
    source_states = document["model_states"]
    if type(source_states) is not dict or set(source_states) != set(HORIZONS):
        raise ValueError("Exactly 13 horizon-specific mock multi-feature states required")
    states = {horizon: _mock_state(source_states[horizon]) for horizon in HORIZONS}
    if payload != _canonical_bytes(document):
        raise ValueError("Exact canonical JSON bytes required")
    return {
        "status": "SYNTHETIC_MULTIFEATURE_STATE_BYTES_ONLY",
        "model_states": states,
        "local_bundle_sha256": actual,
        "local_state_sha256_by_horizon": {
            horizon: hashlib.sha256(_canonical_bytes(states[horizon])).hexdigest()
            for horizon in HORIZONS
        },
        "trained_model_authenticated": False,
        "publisher_signature_verified": False,
        "historical_vintage_verified": False,
        "real_data_authorized": False,
        "scientific_authorization": "NO_RUN",
        "stage7_freeze_authorized": False,
    }


def _mock_row(row: object, window: dict[str, object]) -> tuple[float, ...]:
    if type(row) is not dict or set(row) != ROW_KEYS:
        raise ValueError("Exact synthetic feature row required, no labels")
    if type(row["horizon"]) is not str or row["horizon"] != window["horizon"]:
        raise ValueError("Synthetic feature horizon differs from forecast window")
    names = _names(row["feature_group"], row["feature_names"])
    values = row["values"]
    if type(values) is not list or len(values) != len(names):
        raise ValueError("Synthetic feature vector dimension mismatch")
    observed, _ = _utc_timestamp(row["observed_at_utc"], "synthetic feature observation")
    if not window["origin_cutoff_utc"] <= observed <= window["forecast_issued_at_utc"]:
        raise ValueError("Synthetic feature observed after issuance or before close")
    return tuple(_finite_coefficient(value, "synthetic feature") for value in values)


def _ridge_signal(
    weights: tuple[float, ...],
    means: tuple[float, ...],
    scales: tuple[float, ...],
    values: tuple[float, ...],
) -> float:
    """Compare existing arithmetic against stable summation; reject lost terms."""
    terms: list[float] = []
    for index, value in enumerate(values):
        centered = value - means[index]
        if value != means[index] and centered == 0.0:
            raise ValueError("Mock hybrid feature difference rounded to zero")
        raw = weights[index + 1] * centered
        if weights[index + 1] != 0.0 and centered != 0.0 and raw == 0.0:
            raise ValueError("Mock hybrid ridge term underflow")
        term = raw / scales[index]
        if raw != 0.0 and term == 0.0:
            raise ValueError("Mock hybrid scaled ridge term underflow")
        if not math.isfinite(term):
            raise ValueError("Mock hybrid ridge term is nonfinite")
        terms.append(term)
    reference = math.fsum([weights[0], *terms])
    predicted = _estimate(weights, means, scales, values)
    if not math.isfinite(predicted):
        raise ValueError("Existing hybrid estimate returned nonfinite")
    if reference != 0.0 and (predicted == 0.0 or (reference > 0) != (predicted > 0)):
        raise ValueError("Existing hybrid estimate lost a nonzero signed signal")
    return predicted


def bridge_synthetic_multifeature_bundle(
    windows: list[dict[str, object]],
    feature_rows: list[dict[str, object]],
    payload: bytes,
    expected_local_sha256: str,
) -> dict[str, object]:
    """Mock 5/8/10/12-d feature equations -> 13-horizon output contract."""
    if type(windows) is not list or len(windows) != len(HORIZONS):
        raise ValueError("Exactly 13 synthetic forecast windows required")
    if type(feature_rows) is not list or len(feature_rows) != len(HORIZONS):
        raise ValueError("Exactly 13 synthetic feature rows required")
    bundle = inspect_synthetic_multifeature_bundle(payload, expected_local_sha256)
    states = bundle["model_states"]
    inspected = [_inspect_synthetic_window(window) for window in windows]
    if len({row["horizon"] for row in inspected}) != len(HORIZONS):
        raise ValueError("Missing or duplicate synthetic forecast horizon")
    rows_by_horizon: dict[str, dict[str, object]] = {}
    for row in feature_rows:
        if type(row) is not dict or type(row.get("horizon")) is not str:
            raise ValueError("Invalid synthetic feature horizon")
        horizon = row["horizon"]
        if horizon not in HORIZONS or horizon in rows_by_horizon:
            raise ValueError("Unknown or duplicate synthetic feature horizon")
        rows_by_horizon[horizon] = row
    if set(rows_by_horizon) != set(HORIZONS):
        raise ValueError("Incomplete synthetic feature horizon set")

    outputs: list[dict[str, object]] = []
    for window in inspected:
        horizon = str(window["horizon"])
        state = states[horizon]
        values = _mock_row(rows_by_horizon[horizon], window)
        if (
            rows_by_horizon[horizon]["feature_group"] != state["feature_group"]
            or rows_by_horizon[horizon]["feature_names"] != state["feature_names"]
        ):
            raise ValueError("Synthetic feature vector differs from mock model layout")
        if state["last_training_target_utc"] > window["origin_cutoff_utc"]:
            raise ValueError("Mock training label extends beyond forecast origin")
        if state["model_created_at_utc"] > window["forecast_issued_at_utc"]:
            raise ValueError("Mock model created after claimed forecast issuance")
        weights = tuple(state["weights"])
        means = tuple(state["means"])
        scales = tuple(state["scales"])
        signal = _ridge_signal(weights, means, scales, values)
        blend = float(state["blend"])
        mixed = blend * signal
        if blend != 0.0 and signal != 0.0 and mixed == 0.0:
            raise ValueError("Synthetic blend lost a nonzero Ridge signal")
        origin_price = float(window["origin_price_usd"])
        point = origin_price * math.exp(max(-1.0, min(1.0, mixed)))
        if not math.isfinite(point) or point <= 0:
            raise ValueError("Mock multi-feature forecast price is unrepresentable")
        if mixed != 0.0 and point == origin_price:
            raise ValueError("Mock multi-feature forecast lost direction")
        lo80, hi80, lo95, hi95 = _illustrative_intervals(point)
        outputs.append(
            {
                "horizon": horizon,
                "origin_cutoff_utc": window["origin_cutoff_utc"],
                "forecast_issued_at_utc": window["forecast_issued_at_utc"],
                "target_end_utc": window["target_end_utc"],
                "source_market_id": window["source_market_id"],
                "origin_price_usd": origin_price,
                "predicted_target_price_usd": point,
                "predicted_direction": (
                    "up" if point > origin_price else "down" if point < origin_price else "flat"
                ),
                "interval_80_low_usd": lo80,
                "interval_80_high_usd": hi80,
                "interval_95_low_usd": lo95,
                "interval_95_high_usd": hi95,
                "model_code_sha256": state["model_code_sha256"],
                "feature_code_sha256": window["feature_code_sha256"],
                "dataset_manifest_sha256": window["dataset_manifest_sha256"],
            }
        )
    return {
        "status": "SYNTHETIC_MULTIFEATURE_HYBRID_COMPATIBILITY_ONLY",
        "forecast_batch": validate_full_13_horizon_batch(outputs),
        "local_bundle_sha256": bundle["local_bundle_sha256"],
        "feature_group_dimensions": {group: len(names) for group, names in FEATURE_LAYOUTS.items()},
        "existing_daily_hybrid_multihorizon_training_supported": False,
        "actual_model_artifacts_loaded": False,
        "trained_model_authenticated": False,
        "feature_first_availability_authenticated": False,
        "predictive_accuracy_evaluated": False,
        "interval_80_95_calibrated": False,
        "scientific_authorization": "NO_RUN",
        "stage7_freeze_authorized": False,
    }
