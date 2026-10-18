"""Entirely hand-constructed dataclasses; NO fitted checkpoint or real data."""

from __future__ import annotations

import math
from datetime import UTC, date, datetime

import pytest
from scripts.stage6_dual_target_forecast_contract import HORIZONS
from scripts.stage6_existing_model_metadata_audit import (
    inspect_existing_model_all_13,
    inspect_existing_model_horizon_metadata,
)
from scripts.stage6_synthetic_multifeature_ridge_adapter import FEATURE_LAYOUTS

from crypto_intelligence_os.ai_forecasting import TrainedModel
from crypto_intelligence_os.hybrid_forecasting import HybridModel

ORIGIN = int(datetime(2026, 1, 2, tzinfo=UTC).timestamp())
EARLIER = date(2025, 12, 1)


def _hybrid(
    horizon_days: int = 2, feature_group: str = "all", **changes: object
) -> HybridModel:
    n = len(FEATURE_LAYOUTS[feature_group])
    data: dict[str, object] = {
        "horizon_days": horizon_days,
        "weights": (0.0,) * (n + 1),
        "means": (0.0,) * n,
        "scales": (1.0,) * n,
        "blend": 0.5,
        "train_examples": 100,
        "last_training_target": EARLIER,
        "feature_group": feature_group,
    }
    data.update(changes)
    return HybridModel(**data)


def _linear(horizon_days: int = 1, **changes: object) -> TrainedModel:
    data: dict[str, object] = {
        "horizon_days": horizon_days,
        "intercept": 0.0,
        "coefficients": (0.0, 0.1, -0.1),
        "train_examples": 50,
        "last_training_target": EARLIER,
    }
    data.update(changes)
    return TrainedModel(**data)


@pytest.mark.parametrize(
    ("days", "horizon"),
    [(1, "1d"), (2, "2d"), (3, "3d")],
)
def test_only_matching_daily_target_can_have_metadata_shape_compatibility(
    days: int, horizon: str
) -> None:
    for model in (_hybrid(horizon_days=days), _linear(horizon_days=days)):
        result = inspect_existing_model_horizon_metadata(model, horizon, ORIGIN)
        assert result["candidate_shape_compatible"] is True
        assert result["status"] == "DAILY_SHAPE_COMPATIBLE_BUT_UNVERIFIED"
        assert result["model_eligible_for_real_execution"] is False
        assert result["actual_fitted_weights_authenticated"] is False
        assert result["training_labels_first_available_verified"] is False
        assert result["scientific_authorization"] == "NO_RUN"


@pytest.mark.parametrize("horizon", list(HORIZONS))
def test_same_mock_hybrid_cannot_impersonate_thirteen_fitted_horizons(horizon: str) -> None:
    inspected = inspect_existing_model_horizon_metadata(_hybrid(2), horizon, ORIGIN)
    assert inspected["candidate_shape_compatible"] is (horizon == "2d")
    assert inspected["model_eligible_for_real_execution"] is False


@pytest.mark.parametrize("model", [_hybrid(7), _linear(7), _hybrid(30), _linear(30)])
def test_daily_7_and_30_day_targets_do_not_prove_week_or_calendar_month(
    model: object
) -> None:
    for horizon in ("1w", "1mo"):
        result = inspect_existing_model_horizon_metadata(model, horizon, ORIGIN)
        assert "existing_research_trainer_has_daily_targets_only" in result[
            "incompatibility_reasons"
        ]
        assert result["candidate_shape_compatible"] is False


@pytest.mark.parametrize("group,n", [
    ("all", 12),
    ("no_halving", 10),
    ("no_extrema", 8),
    ("momentum_only", 5),
])
def test_real_hybrid_class_group_dimensions_recognized(group: str, n: int) -> None:
    result = inspect_existing_model_horizon_metadata(
        _hybrid(feature_group=group), "2d", ORIGIN
    )
    assert result["dimension"] == n
    assert result["feature_group"] == group


def test_full_thirteen_horizon_matrix_has_only_one_shape_match() -> None:
    result = inspect_existing_model_all_13(_hybrid(horizon_days=3), ORIGIN)
    assert result["horizon_count"] == 13
    assert result["shape_compatible_horizon_count"] == 1
    assert [item["requested_horizon"] for item in result["horizons"]] == list(HORIZONS)
    assert [
        item["requested_horizon"] for item in result["horizons"]
        if item["candidate_shape_compatible"]
    ] == ["3d"]
    assert result["real_model_execution_authorized"] is False
    assert result["stage7_freeze_authorized"] is False


@pytest.mark.parametrize("bad", [date(2026, 1, 2), date(2026, 1, 3)])
def test_unresolved_last_training_target_day_cannot_be_called_compatible(
    bad: date
) -> None:
    result = inspect_existing_model_horizon_metadata(
        _hybrid(last_training_target=bad), "2d", ORIGIN
    )
    assert "last_training_target_date_not_strictly_before_origin_date" in result[
        "incompatibility_reasons"
    ]


@pytest.mark.parametrize("bad", [True, 0, -1, 1.5, "3"])
def test_invalid_claimed_training_size_is_rejected(bad: object) -> None:
    with pytest.raises(ValueError, match="train_examples"):
        inspect_existing_model_horizon_metadata(_hybrid(train_examples=bad), "2d", ORIGIN)


@pytest.mark.parametrize("bad", [True, 0, -1, "2"])
def test_invalid_target_day_count_is_rejected(bad: object) -> None:
    with pytest.raises(ValueError, match="horizon_days"):
        inspect_existing_model_horizon_metadata(_hybrid(horizon_days=bad), "2d", ORIGIN)


@pytest.mark.parametrize("bad", [math.nan, math.inf, True, 1001.0])
def test_invalid_hybrid_weights_fail_closed(bad: object) -> None:
    model = _hybrid(weights=(0.0, bad, *([0.0] * 11)))
    with pytest.raises(ValueError, match="weight"):
        inspect_existing_model_horizon_metadata(model, "2d", ORIGIN)


@pytest.mark.parametrize("bad", [0.0, -1.0, math.nan])
def test_hybrid_scale_must_be_positive_and_finite(bad: float) -> None:
    model = _hybrid(scales=(bad, *([1.0] * 11)))
    with pytest.raises(ValueError, match="scale"):
        inspect_existing_model_horizon_metadata(model, "2d", ORIGIN)


def test_malformed_shape_and_unknown_hybrid_group_rejected() -> None:
    with pytest.raises(ValueError, match="dimensions"):
        inspect_existing_model_horizon_metadata(_hybrid(weights=(0.0,)), "2d", ORIGIN)
    with pytest.raises(ValueError, match="feature group"):
        inspect_existing_model_horizon_metadata(
            HybridModel(**{**_hybrid().__dict__, "feature_group": "invented"}), "2d", ORIGIN
        )


@pytest.mark.parametrize("bad", [1.1, -0.1, True])
def test_invalid_hybrid_blend_rejected(bad: object) -> None:
    with pytest.raises(ValueError, match="blend"):
        inspect_existing_model_horizon_metadata(_hybrid(blend=bad), "2d", ORIGIN)


def test_invalid_linear_regression_shape_and_coefficients_rejected() -> None:
    for model in (
        _linear(coefficients=(0.1, 0.2)),
        _linear(coefficients=(0.1, 0.2, math.inf)),
    ):
        with pytest.raises(ValueError, match=r"coefficients|coefficient"):
            inspect_existing_model_horizon_metadata(model, "1d", ORIGIN)


def test_non_daily_and_noncanonical_origin_fail_to_gain_compatibility() -> None:
    date_time = ORIGIN + 60
    bad = inspect_existing_model_horizon_metadata(_hybrid(1), "1d", date_time)
    assert bad["candidate_shape_compatible"] is False
    assert "noncanonical_daily_origin" in bad["incompatibility_reasons"]
    weekly = inspect_existing_model_horizon_metadata(_hybrid(7), "1w", ORIGIN)
    assert weekly["candidate_shape_compatible"] is False


def test_untrusted_model_subclasses_and_missing_classes_rejected() -> None:
    class HybridSubclass(HybridModel):
        pass

    with pytest.raises(ValueError, match="exact in-memory existing"):
        inspect_existing_model_horizon_metadata(HybridSubclass(**_hybrid().__dict__), "2d", ORIGIN)
    with pytest.raises(ValueError, match="exact in-memory existing"):
        inspect_existing_model_horizon_metadata({"weights": []}, "1d", ORIGIN)


def test_bad_horizon_and_clock_value_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown requested"):
        inspect_existing_model_horizon_metadata(_hybrid(), "90d", ORIGIN)
    with pytest.raises(ValueError, match="positive"):
        inspect_existing_model_horizon_metadata(_hybrid(), "2d", True)


def test_diagnostic_never_contains_actual_model_coefficients() -> None:
    result = inspect_existing_model_horizon_metadata(_hybrid(), "2d", ORIGIN)
    assert "weights" not in result
    assert "means" not in result
    assert "scales" not in result
    assert result["checkpoint_bytes_loaded"] is False
    assert result["independent_artifact_custody_verified"] is False
