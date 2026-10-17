"""In-memory integrity gate for MOCK 13-horizon Ridge states, never real model artifacts.

A SHA-256 of caller-supplied bytes detects mismatch only: it is NOT evidence of
who trained a model, what data were known at any cutoff, or authentic issuance.
No filesystem, network, training, model registry or provider access.
"""

from __future__ import annotations

import hashlib
import hmac
import json

from scripts.stage6_dual_target_forecast_contract import HORIZONS, _digest
from scripts.stage6_synthetic_ridge_inference_bridge import (
    _validated_mock_state,
    bridge_mock_ridge_to_13_horizon_contract,
)

FORMAT = "stage6-synthetic-ridge-bundle-v1"
MAX_BUNDLE_BYTES = 65_536
BUNDLE_KEYS = frozenset(
    {"format", "classification", "model_states", "real_data_authorized"}
)


def _no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object key in synthetic model bundle")
        result[key] = value
    return result


def _reject_nonjson_number(value: str) -> None:
    raise ValueError(f"Forbidden nonfinite JSON number: {value}")


def _canonical_bytes(document: object) -> bytes:
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def inspect_in_memory_mock_bundle(
    payload: bytes,
    expected_local_sha256: str,
) -> dict[str, object]:
    """Parse exact canonical untrusted mock bytes without inferring provenance.

    Only caller-owned memory is read. The expected digest is ALSO caller-supplied,
    hence matching it never authenticates a publisher, time, license or custodian.
    """
    if type(payload) is not bytes or not 0 < len(payload) <= MAX_BUNDLE_BYTES:
        raise ValueError("Synthetic bundle must be bounded nonempty plain bytes")
    expected = _digest(expected_local_sha256, "expected bundle digest")
    actual = hashlib.sha256(payload).hexdigest()
    if not hmac.compare_digest(actual, expected):
        raise ValueError("Synthetic bundle SHA-256 mismatch")
    try:
        document = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_no_duplicate_keys,
            parse_constant=_reject_nonjson_number,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Malformed UTF-8 JSON synthetic bundle") from exc
    if type(document) is not dict or set(document) != BUNDLE_KEYS:
        raise ValueError("Unexpected synthetic bundle metadata or forbidden extra fields")
    if (
        document["format"] != FORMAT
        or type(document["format"]) is not str
        or type(document["classification"]) is not str
        or document["classification"] != "MOCK_ONLY"
        or document["real_data_authorized"] is not False
    ):
        raise ValueError("Only explicit mock-only, NO_RUN bundle format accepted")
    states = document["model_states"]
    if type(states) is not dict or set(states) != set(HORIZONS):
        raise ValueError("Mock bundle requires exactly 13 horizon-specific states")
    # Validate numbers, state shapes and digest formats BEFORE canonicalizing.
    validated = {horizon: _validated_mock_state(states[horizon]) for horizon in HORIZONS}
    if _canonical_bytes(document) != payload:
        raise ValueError("Synthetic bundle must use exact canonical UTF-8 JSON encoding")
    # Rebuild and deep-copy plain model states. No arbitrary metadata or objects.
    plain_states = {
        horizon: {
            "weights": list(validated[horizon][0]),
            "means": list(validated[horizon][1]),
            "scales": list(validated[horizon][2]),
            "model_code_sha256": validated[horizon][3],
        }
        for horizon in HORIZONS
    }
    per_state_hashes = {
        horizon: hashlib.sha256(_canonical_bytes(plain_states[horizon])).hexdigest()
        for horizon in HORIZONS
    }
    return {
        "status": "SYNTHETIC_BUNDLE_BYTES_CHECKED_ONLY",
        "model_states": plain_states,
        "local_bundle_sha256": actual,
        "local_mock_state_sha256_by_horizon": per_state_hashes,
        "caller_bytes_match_caller_digest": True,
        "trained_model_authenticated": False,
        "publisher_signature_verified": False,
        "immutable_external_custody_verified": False,
        "data_first_availability_verified": False,
        "license_verified": False,
        "scientific_authorization": "NO_RUN",
        "stage7_freeze_authorized": False,
    }


def bridge_in_memory_mock_bundle(
    windows: list[dict[str, object]],
    bundle_bytes: bytes,
    expected_local_sha256: str,
) -> dict[str, object]:
    """Feed inspected MOCK states into the existing synthetic 13-horizon bridge."""
    inspected = inspect_in_memory_mock_bundle(bundle_bytes, expected_local_sha256)
    forecast = bridge_mock_ridge_to_13_horizon_contract(
        windows, inspected["model_states"]
    )
    return {
        "status": "SYNTHETIC_BUNDLE_RIDGE_BRIDGE_ONLY",
        "local_bundle_sha256": inspected["local_bundle_sha256"],
        "local_mock_state_sha256_by_horizon": inspected[
            "local_mock_state_sha256_by_horizon"
        ],
        "caller_bytes_match_caller_digest": True,
        "forecast_batch": forecast["forecast_batch"],
        "trained_model_authenticated": False,
        "publisher_signature_verified": False,
        "data_first_availability_verified": False,
        "immutable_external_custody_verified": False,
        "license_verified": False,
        "real_data_evaluated": False,
        "forecast_accuracy_evaluated": False,
        "interval_80_95_calibrated": False,
        "scientific_authorization": "NO_RUN",
        "stage7_freeze_authorized": False,
    }
