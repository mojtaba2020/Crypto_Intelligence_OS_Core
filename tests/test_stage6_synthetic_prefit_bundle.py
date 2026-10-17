"""No data file, real fitting or outcomes: only deliberately invented model states."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime

import pytest
from scripts.stage6_dual_target_forecast_contract import HORIZONS
from scripts.stage6_synthetic_prefit_bundle import (
    FORMAT,
    MAX_BUNDLE_BYTES,
    bridge_in_memory_mock_bundle,
    inspect_in_memory_mock_bundle,
)

JAN_1 = int(datetime(2026, 1, 1, tzinfo=UTC).timestamp())
JAN_2 = int(datetime(2026, 1, 2, tzinfo=UTC).timestamp())
MONDAY = int(datetime(2026, 1, 5, tzinfo=UTC).timestamp())
DEC_1 = int(datetime(2025, 12, 1, tzinfo=UTC).timestamp())


def _states() -> dict[str, dict]:
    return {
        horizon: {
            "weights": [0.0, 0.5],
            "means": [0.0],
            "scales": [1.0],
            "model_code_sha256": "e" * 64,
        }
        for horizon in HORIZONS
    }


def _envelope() -> dict:
    return {
        "format": FORMAT,
        "classification": "MOCK_ONLY",
        "real_data_authorized": False,
        "model_states": _states(),
    }


def _encode(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _windows() -> list[dict]:
    result = []
    for horizon, (family, _) in HORIZONS.items():
        if family == "monthly":
            origin, previous = JAN_1, DEC_1
        elif family == "weekly":
            origin, previous = MONDAY, MONDAY - 7 * 86400
        elif family == "daily":
            origin, previous = JAN_2, JAN_1
        else:
            origin, previous = JAN_2, JAN_2 - 3600
        result.append(
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
    return result


def test_canonical_mock_bytes_roundtrip_without_claiming_external_provenance() -> None:
    payload = _encode(_envelope())
    record = inspect_in_memory_mock_bundle(payload, _sha(payload))
    assert record["caller_bytes_match_caller_digest"] is True
    assert record["local_bundle_sha256"] == _sha(payload)
    assert set(record["model_states"]) == set(HORIZONS)
    assert set(record["local_mock_state_sha256_by_horizon"]) == set(HORIZONS)
    for flag in (
        "trained_model_authenticated",
        "publisher_signature_verified",
        "immutable_external_custody_verified",
        "data_first_availability_verified",
        "license_verified",
        "stage7_freeze_authorized",
    ):
        assert record[flag] is False
    assert record["scientific_authorization"] == "NO_RUN"


def test_same_state_bytes_produce_same_local_digest() -> None:
    payload = _encode(_envelope())
    a = inspect_in_memory_mock_bundle(payload, _sha(payload))
    b = inspect_in_memory_mock_bundle(bytes(payload), _sha(payload))
    assert a["local_mock_state_sha256_by_horizon"] == b["local_mock_state_sha256_by_horizon"]


def test_in_memory_mock_bundle_calls_existing_13_horizon_ridge_bridge() -> None:
    payload = _encode(_envelope())
    result = bridge_in_memory_mock_bundle(_windows(), payload, _sha(payload))
    assert result["local_bundle_sha256"] == _sha(payload)
    assert result["status"] == "SYNTHETIC_BUNDLE_RIDGE_BRIDGE_ONLY"
    assert result["forecast_batch"]["horizon_count"] == 13
    assert [r["horizon"] for r in result["forecast_batch"]["forecasts"]] == list(HORIZONS)
    assert all(r["predicted_direction"] == "up" for r in result["forecast_batch"]["forecasts"])
    assert result["real_data_evaluated"] is False
    assert result["forecast_accuracy_evaluated"] is False
    assert result["interval_80_95_calibrated"] is False
    assert result["trained_model_authenticated"] is False
    assert result["scientific_authorization"] == "NO_RUN"


@pytest.mark.parametrize("bad", [b"", b"x" * (MAX_BUNDLE_BYTES + 1), "not bytes", bytearray(b"a")])
def test_reject_unbounded_or_non_plain_bytes(bad: object) -> None:
    with pytest.raises(ValueError, match="bounded nonempty plain bytes"):
        inspect_in_memory_mock_bundle(bad, "a" * 64)


def test_reject_modified_payload_against_original_claimed_digest() -> None:
    payload = _encode(_envelope())
    changed = payload.replace(b'"weights":[0.0,0.5]', b'"weights":[0.0,0.6]', 1)
    assert changed != payload
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        inspect_in_memory_mock_bundle(changed, _sha(payload))


@pytest.mark.parametrize("bad_digest", ["A" * 64, "f" * 63, "nonhash", True])
def test_reject_malformed_claimed_digests(bad_digest: object) -> None:
    payload = _encode(_envelope())
    with pytest.raises(ValueError, match="SHA-256"):
        inspect_in_memory_mock_bundle(payload, bad_digest)


def test_duplicate_json_keys_rejected_even_when_hash_matches_forged_bytes() -> None:
    payload = _encode(_envelope())
    changed = payload.replace(
        b'"classification":"MOCK_ONLY"',
        b'"classification":"MOCK_ONLY","classification":"MOCK_ONLY"',
        1,
    )
    with pytest.raises(ValueError, match="Duplicate JSON object key"):
        inspect_in_memory_mock_bundle(changed, _sha(changed))


def test_noncanonical_whitespace_cannot_pass_with_its_own_matching_sha() -> None:
    payload = json.dumps(_envelope(), sort_keys=True).encode("utf-8")
    with pytest.raises(ValueError, match="canonical UTF-8 JSON"):
        inspect_in_memory_mock_bundle(payload, _sha(payload))


@pytest.mark.parametrize("field", ["publisher_signature", "actual_future_price", "private_key"])
def test_no_extra_or_outcome_fields_in_bundle(field: str) -> None:
    document = _envelope()
    document[field] = "junk"
    payload = _encode(document)
    with pytest.raises(ValueError, match="Unexpected synthetic bundle metadata"):
        inspect_in_memory_mock_bundle(payload, _sha(payload))


def test_training_authorization_claim_and_real_classification_are_rejected() -> None:
    for field, bad in (
        ("classification", "TRAINED_REAL_DATA"),
        ("real_data_authorized", True),
        ("format", "stage6-live-model-bundle-v1"),
    ):
        document = _envelope()
        document[field] = bad
        payload = _encode(document)
        with pytest.raises(ValueError, match="mock-only"):
            inspect_in_memory_mock_bundle(payload, _sha(payload))


@pytest.mark.parametrize("missing", ["1h", "3mo"])
def test_missing_horizon_specific_model_state_is_rejected(missing: str) -> None:
    document = _envelope()
    del document["model_states"][missing]
    payload = _encode(document)
    with pytest.raises(ValueError, match="exactly 13"):
        inspect_in_memory_mock_bundle(payload, _sha(payload))


def test_state_disallows_target_label_injection() -> None:
    document = _envelope()
    document["model_states"]["1h"]["target_label"] = 1
    payload = _encode(document)
    with pytest.raises(ValueError, match="Exact mock model state"):
        inspect_in_memory_mock_bundle(payload, _sha(payload))


@pytest.mark.parametrize("bad", [True, "0.5", 1e9, math.nan])
def test_invalid_state_weights_fail_before_forecast_creation(bad: object) -> None:
    document = _envelope()
    document["model_states"]["1h"]["weights"][1] = bad
    if isinstance(bad, float) and math.isnan(bad):
        payload = _encode(_envelope()).replace(b'"weights":[0.0,0.5]', b'"weights":[0.0,NaN]', 1)
        with pytest.raises(ValueError, match="Forbidden nonfinite JSON number"):
            inspect_in_memory_mock_bundle(payload, _sha(payload))
        return
    payload = _encode(document)
    with pytest.raises(ValueError, match="coefficient"):
        inspect_in_memory_mock_bundle(payload, _sha(payload))


def test_invalid_utf8_and_invalid_json_fail_without_artifact_io() -> None:
    for payload in (b"\xff\xfe", b'{"broken":'):
        with pytest.raises(ValueError, match="Malformed UTF-8 JSON"):
            inspect_in_memory_mock_bundle(payload, _sha(payload))


def test_zero_mock_coefficients_keep_flat_price_implied_direction() -> None:
    document = _envelope()
    for item in document["model_states"].values():
        item["weights"] = [0.0, 0.0]
    payload = _encode(document)
    report = bridge_in_memory_mock_bundle(_windows(), payload, _sha(payload))
    assert all(
        row["predicted_direction"] == "flat" for row in report["forecast_batch"]["forecasts"]
    )


def test_real_input_window_cannot_smuggle_later_observation() -> None:
    windows = _windows()
    windows[0]["origin_observed_at_utc"] = windows[0]["forecast_issued_at_utc"] + 1
    payload = _encode(_envelope())
    with pytest.raises(ValueError, match="later than claimed issuance"):
        bridge_in_memory_mock_bundle(windows, payload, _sha(payload))
