"""Read-only model CLASS/shape diagnostics against the 13 requested horizon IDs.

Only accepts instances of the existing, in-memory research dataclasses.
Never loads weights from disk, deserializes untrusted objects, fits, predicts,
scores outcomes or grants model/data/source/runner authorization.
"""

from __future__ import annotations

from datetime import date

from scripts.stage6_dual_target_forecast_contract import HORIZONS, _utc_timestamp
from scripts.stage6_synthetic_multifeature_ridge_adapter import FEATURE_LAYOUTS
from scripts.stage6_synthetic_ridge_inference_bridge import _finite_coefficient

from crypto_intelligence_os.ai_forecasting import TrainedModel
from crypto_intelligence_os.hybrid_forecasting import HybridModel

DAILY_TARGET_IDS = {1: "1d", 2: "2d", 3: "3d"}


def _check_metadata_shape(model: TrainedModel | HybridModel) -> dict[str, object]:
    """Reject invalid in-memory research model STRUCTURE, never authenticate fit."""
    if type(model.horizon_days) is not int or model.horizon_days <= 0:
        raise ValueError("Model horizon_days must be a positive integer")
    if type(model.train_examples) is not int or model.train_examples <= 0:
        raise ValueError("Model train_examples must be a positive integer")
    if type(model.last_training_target) is not date:
        raise ValueError("Training target must be an exact calendar date")

    if type(model) is TrainedModel:
        coefficients = model.coefficients
        if type(coefficients) is not tuple or len(coefficients) != 3:
            raise ValueError("Existing linear baseline requires three coefficients")
        _finite_coefficient(model.intercept, "linear intercept")
        for coef in coefficients:
            _finite_coefficient(coef, "linear coefficient")
        return {"model_type": "ai_forecasting.TrainedModel", "dimension": 3}

    if type(model.feature_group) is not str or model.feature_group not in FEATURE_LAYOUTS:
        raise ValueError("Unknown existing Hybrid feature group")
    dimension = len(FEATURE_LAYOUTS[model.feature_group])
    if (
        type(model.weights) is not tuple
        or len(model.weights) != dimension + 1
        or type(model.means) is not tuple
        or len(model.means) != dimension
        or type(model.scales) is not tuple
        or len(model.scales) != dimension
    ):
        raise ValueError("Existing Hybrid dimensions do not match production feature group")
    for value in model.weights:
        _finite_coefficient(value, "Hybrid weight")
    for value in model.means:
        _finite_coefficient(value, "Hybrid mean")
    for value in model.scales:
        if _finite_coefficient(value, "Hybrid scale") < 1e-8:
            raise ValueError("Hybrid scale must be nondegenerate and positive")
    blend = _finite_coefficient(model.blend, "Hybrid blend")
    if not 0.0 <= blend <= 1.0:
        raise ValueError("Hybrid blend must be between zero and one")
    return {
        "model_type": "hybrid_forecasting.HybridModel",
        "feature_group": model.feature_group,
        "dimension": dimension,
    }


def inspect_existing_model_horizon_metadata(
    model: object, requested_horizon: str, origin_cutoff_utc: int
) -> dict[str, object]:
    """Determine only structural fit of a caller-owned research object.

    A compatible SHAPE is not a valid point-in-time checkpoint. Existing
    model dataclasses have NO model-creation time, data/venue identifiers,
    independent signature, immutable archive receipt or artifact-file hash.
    """
    if type(model) not in (HybridModel, TrainedModel):
        raise ValueError("Only exact in-memory existing research model classes accepted")
    if type(requested_horizon) is not str or requested_horizon not in HORIZONS:
        raise ValueError("Unknown requested BTC horizon identifier")
    _, origin = _utc_timestamp(origin_cutoff_utc, "requested forecast origin")
    metadata = _check_metadata_shape(model)
    family, _ = HORIZONS[requested_horizon]
    reasons: list[str] = []
    if family != "daily":
        reasons.append("existing_research_trainer_has_daily_targets_only")
    elif DAILY_TARGET_IDS.get(model.horizon_days) != requested_horizon:
        reasons.append("trained_daily_target_horizon_does_not_match_requested_id")
    if model.last_training_target >= origin.date():
        reasons.append("last_training_target_date_not_strictly_before_origin_date")
    if family == "daily" and (origin.hour or origin.minute or origin.second):
        reasons.append("noncanonical_daily_origin")
    shape_compatible = not reasons

    return {
        "status": (
            "DAILY_SHAPE_COMPATIBLE_BUT_UNVERIFIED"
            if shape_compatible else "INCOMPATIBLE_OR_UNRESOLVED_MODEL_METADATA"
        ),
        "requested_horizon": requested_horizon,
        "original_model_horizon_days": model.horizon_days,
        "last_training_target_day": model.last_training_target.isoformat(),
        "reported_training_example_count": model.train_examples,
        "origin_cutoff_utc": origin_cutoff_utc,
        "candidate_shape_compatible": shape_compatible,
        "incompatibility_reasons": reasons,
        **metadata,
        "model_creation_timestamp_present": False,
        "model_source_asset_venue_identity_present": False,
        "training_labels_first_available_verified": False,
        "actual_fitted_weights_authenticated": False,
        "checkpoint_bytes_loaded": False,
        "independent_artifact_custody_verified": False,
        "predictive_accuracy_evaluated": False,
        "model_eligible_for_real_execution": False,
        "scientific_authorization": "NO_RUN",
        "stage7_freeze_authorized": False,
    }


def inspect_existing_model_all_13(
    model: object, origin_cutoff_utc: int
) -> dict[str, object]:
    """Report an exact 13-row compatibility matrix, never execute forecasts."""
    results = [
        inspect_existing_model_horizon_metadata(model, horizon, origin_cutoff_utc)
        for horizon in HORIZONS
    ]
    return {
        "status": "MODEL_CLASS_METADATA_DIAGNOSTIC_ONLY",
        "horizon_count": len(results),
        "shape_compatible_horizon_count": sum(
            int(row["candidate_shape_compatible"]) for row in results
        ),
        "horizons": results,
        "real_model_execution_authorized": False,
        "scientific_authorization": "NO_RUN",
        "stage7_freeze_authorized": False,
    }
