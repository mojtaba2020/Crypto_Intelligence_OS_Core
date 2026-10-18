"""Adversarial all-synthetic multi-feature Ridge compatibility tests."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, date, datetime, timedelta

import pytest
from scripts.stage6_dual_target_forecast_contract import HORIZONS
from scripts.stage6_synthetic_multifeature_ridge_adapter import (
    FEATURE_LAYOUTS,
    FORMAT,
    bridge_synthetic_multifeature_bundle,
    inspect_synthetic_multifeature_bundle,
)

from crypto_intelligence_os.ai_forecasting import Observation
from crypto_intelligence_os.hybrid_forecasting import _estimate, features

JAN_1 = int(datetime(2026, 1, 1, tzinfo=UTC).timestamp())
JAN_2 = int(datetime(2026, 1, 2, tzinfo=UTC).timestamp())
MON = int(datetime(2026, 1, 5, tzinfo=UTC).timestamp())
DEC_1 = int(datetime(2025, 12, 1, tzinfo=UTC).timestamp())
NOV_1 = int(datetime(2025, 11, 1, tzinfo=UTC).timestamp())
NOV_2 = int(datetime(2025, 11, 2, tzinfo=UTC).timestamp())
GROUPS = ("all", "no_halving", "no_extrema", "momentum_only")


def _encode(document: object) -> bytes:
    return json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _windows() -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for horizon, (family, _) in HORIZONS.items():
        if family == "monthly":
            origin, previous = JAN_1, DEC_1
        elif family == "weekly":
            origin, previous = MON, MON - 7 * 86400
        elif family == "daily":
            origin, previous = JAN_2, JAN_1
        else:
            origin, previous = JAN_2, JAN_2 - 3600
        results.append(
            {
                "horizon": horizon,
                "origin_cutoff_utc": origin,
                "previous_cutoff_utc": previous,
                "previous_price_usd": 100.0,
                "origin_price_usd": 110.0,
                "previous_observed_at_utc": previous + 10,
                "origin_observed_at_utc": origin + 10,
                "forecast_issued_at_utc": origin + 60,
                "source_market_id": "bitstamp:BTCUSD:spot",
                "feature_code_sha256": "c" * 64,
                "dataset_manifest_sha256": "d" * 64,
            }
        )
    return results


def _envelope() -> dict[str, object]:
    states: dict[str, object] = {}
    for index, horizon in enumerate(HORIZONS):
        group = GROUPS[index % len(GROUPS)]
        n = len(FEATURE_LAYOUTS[group])
        states[horizon] = {
            "feature_group": group,
            "feature_names": list(FEATURE_LAYOUTS[group]),
            "weights": [0.0, 0.4, *([0.0] * (n - 1))],
            "means": [0.0] * n,
            "scales": [1.0] * n,
            "blend": 0.5,
            "model_code_sha256": "e" * 64,
            "last_training_target_utc": NOV_1,
            "model_created_at_utc": NOV_2,
        }
    return {
        "format": FORMAT,
        "classification": "MOCK_MULTIFEATURE_ONLY",
        "real_data_authorized": False,
        "model_states": states,
    }


def _feature_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for window, group in zip(_windows(), (GROUPS[i % 4] for i in range(13)), strict=True):
        n = len(FEATURE_LAYOUTS[group])
        rows.append(
            {
                "horizon": window["horizon"],
                "feature_group": group,
                "feature_names": list(FEATURE_LAYOUTS[group]),
                "values": [0.1, *([0.0] * (n - 1))],
                "observed_at_utc": window["origin_cutoff_utc"] + 20,
            }
        )
    return rows


def _run(
    *, envelope: dict[str, object] | None = None,
    windows: list[dict[str, object]] | None = None,
    rows: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    data = _encode(_envelope() if envelope is None else envelope)
    return bridge_synthetic_multifeature_bundle(
        _windows() if windows is None else windows,
        _feature_rows() if rows is None else rows,
        data,
        _digest(data),
    )


@pytest.mark.parametrize("group,dimension", [
    ("all", 12),
    ("no_halving", 10),
    ("no_extrema", 8),
    ("momentum_only", 5),
])
def test_layout_pins_actual_existing_hybrid_feature_function(
    group: str, dimension: int
) -> None:
    synthetic = tuple(
        Observation(day=date(2024, 1, 1) + timedelta(days=i), close=100.0 + i)
        for i in range(370)
    )
    computed = features(synthetic, len(synthetic) - 1, group=group)
    assert len(FEATURE_LAYOUTS[group]) == len(computed) == dimension
    assert all(math.isfinite(x) for x in computed)


def test_all_thirteen_horizons_work_with_four_real_feature_layout_sizes() -> None:
    output = _run()
    batch = output["forecast_batch"]
    assert output["feature_group_dimensions"] == {
        "all": 12, "no_halving": 10, "no_extrema": 8, "momentum_only": 5
    }
    assert batch["horizon_count"] == 13
    assert [record["horizon"] for record in batch["forecasts"]] == list(HORIZONS)
    assert all(record["predicted_direction"] == "up" for record in batch["forecasts"])
    actual = 110.0 * math.exp(0.5 * _estimate((0.0, 0.4), (0.0,), (1.0,), (0.1,)))
    assert all(
        record["predicted_target_price_usd"] == pytest.approx(actual)
        for record in batch["forecasts"]
    )
    for name in (
        "existing_daily_hybrid_multihorizon_training_supported",
        "actual_model_artifacts_loaded",
        "trained_model_authenticated",
        "feature_first_availability_authenticated",
        "predictive_accuracy_evaluated",
        "interval_80_95_calibrated",
        "stage7_freeze_authorized",
    ):
        assert output[name] is False
    assert output["scientific_authorization"] == "NO_RUN"


def test_hash_check_is_caller_integrity_only_not_vendor_authentication() -> None:
    payload = _encode(_envelope())
    checked = inspect_synthetic_multifeature_bundle(payload, _digest(payload))
    assert checked["local_bundle_sha256"] == _digest(payload)
    assert checked["publisher_signature_verified"] is False
    assert checked["historical_vintage_verified"] is False
    assert checked["trained_model_authenticated"] is False
    assert len(checked["local_state_sha256_by_horizon"]) == 13
    modified = payload.replace(b'"blend":0.5', b'"blend":0.6', 1)
    assert modified != payload
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        inspect_synthetic_multifeature_bundle(modified, _digest(payload))


@pytest.mark.parametrize("group", GROUPS)
def test_canonical_feature_names_and_order_cannot_be_swapped(group: str) -> None:
    envelope = _envelope()
    state = envelope["model_states"]["1h"]
    state["feature_group"] = group
    state["feature_names"] = list(reversed(FEATURE_LAYOUTS[group]))
    with pytest.raises(ValueError, match="Feature names"):
        _run(envelope=envelope)


def test_wrong_feature_dimension_cannot_masquerade_as_another_group() -> None:
    row = _feature_rows()
    row[0]["values"] = [0.1] * 5
    with pytest.raises(ValueError, match="dimension mismatch"):
        _run(rows=row)


def test_conflicting_feature_group_between_mock_state_and_snapshot_fails() -> None:
    rows = _feature_rows()
    group = "momentum_only"
    rows[0]["feature_group"] = group
    rows[0]["feature_names"] = list(FEATURE_LAYOUTS[group])
    rows[0]["values"] = [0.1] * 5
    with pytest.raises(ValueError, match="differs from mock model layout"):
        _run(rows=rows)


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, True, "0.1", 1e6])
def test_nonfinite_or_out_of_bounds_mock_features_rejected(bad: object) -> None:
    rows = _feature_rows()
    rows[0]["values"][0] = bad
    with pytest.raises(ValueError, match=r"feature.*coefficient"):
        _run(rows=rows)


@pytest.mark.parametrize("name", ["actual_target_price", "future_return", "api_key"])
def test_synthetic_feature_extra_outcome_or_secret_field_rejected(name: str) -> None:
    rows = _feature_rows()
    rows[0][name] = "secret"
    with pytest.raises(ValueError, match="Exact synthetic feature row"):
        _run(rows=rows)


def test_feature_observed_after_forecast_issuance_is_rejected() -> None:
    rows = _feature_rows()
    rows[0]["observed_at_utc"] = JAN_2 + 61
    with pytest.raises(ValueError, match="after issuance"):
        _run(rows=rows)


def test_claimed_last_training_target_after_origin_is_rejected() -> None:
    envelope = _envelope()
    envelope["model_states"]["1h"]["last_training_target_utc"] = JAN_2 + 1
    envelope["model_states"]["1h"]["model_created_at_utc"] = JAN_2 + 2
    with pytest.raises(ValueError, match="training label extends beyond"):
        _run(envelope=envelope)


def test_model_creation_time_after_issuance_is_rejected() -> None:
    envelope = _envelope()
    envelope["model_states"]["1h"]["model_created_at_utc"] = JAN_2 + 61
    with pytest.raises(ValueError, match="created after"):
        _run(envelope=envelope)


def test_blend_zero_means_persistence_as_in_existing_hybrid_formula() -> None:
    envelope = _envelope()
    for state in envelope["model_states"].values():
        state["blend"] = 0.0
    result = _run(envelope=envelope)
    assert all(
        row["predicted_direction"] == "flat"
        for row in result["forecast_batch"]["forecasts"]
    )


@pytest.mark.parametrize("bad", [1.1, -0.1, math.nan, "0.5", True])
def test_hybrid_blend_is_bounded_mock_scalar(bad: object) -> None:
    envelope = _envelope()
    envelope["model_states"]["1h"]["blend"] = bad
    if isinstance(bad, float) and math.isnan(bad):
        raw = _encode(_envelope()).replace(b'"blend":0.5', b'"blend":NaN', 1)
        with pytest.raises(ValueError, match="Forbidden nonfinite JSON number"):
            inspect_synthetic_multifeature_bundle(raw, _digest(raw))
    else:
        with pytest.raises(ValueError, match=r"blend.*coefficient|blend must"):
            _run(envelope=envelope)


def test_subnormal_ridge_slope_cannot_silently_erase_direction() -> None:
    envelope = _envelope()
    for state in envelope["model_states"].values():
        state["weights"][1] = 5e-324
    with pytest.raises(ValueError, match="ridge term underflow"):
        _run(envelope=envelope)


def test_missing_duplicate_and_unexpected_feature_horizons_rejected() -> None:
    rows = _feature_rows()
    rows[0] = rows[1].copy()
    with pytest.raises(ValueError, match="duplicate synthetic feature horizon"):
        _run(rows=rows)
    with pytest.raises(ValueError, match="Exactly 13 synthetic feature rows"):
        _run(rows=_feature_rows()[:-1])


def test_duplicate_json_key_and_noncanonical_bundle_rejected() -> None:
    raw = _encode(_envelope())
    forged = raw.replace(b'"format":', b'"format":"junk","format":', 1)
    with pytest.raises(ValueError, match="Duplicate JSON object key"):
        inspect_synthetic_multifeature_bundle(forged, _digest(forged))
    noncanonical = json.dumps(_envelope(), sort_keys=True).encode()
    with pytest.raises(ValueError, match="canonical JSON"):
        inspect_synthetic_multifeature_bundle(noncanonical, _digest(noncanonical))


def test_synthetic_bundle_never_accepts_real_data_authorization() -> None:
    envelope = _envelope()
    envelope["real_data_authorized"] = True
    with pytest.raises(ValueError, match="Mock-only"):
        _run(envelope=envelope)
