"""Offline cross-check: RFC3161-signed forecast bytes equal one supplied Git append.

The caller must independently authenticate all GitHub objects and TSA trust.
This module performs no network I/O, market scoring, trading or model fitting.
"""

from __future__ import annotations

import json
from collections.abc import Mapping

from scripts.stage6_hourly_elapsed_lead_audit import bind_supplied_git_commit_tree_chain
from scripts.stage6_rfc3161_seal import verify_future_only_rfc3161_seal

_META = frozenset(
    {"version", "issued_at_utc", "origin_hour_utc", "target_close_utc", "horizon_hours"}
)


def crosscheck_signed_forecast_git_append(
    *,
    parent_commit: Mapping[str, object],
    child_commit: Mapping[str, object],
    parent_tree: Mapping[str, object],
    child_tree: Mapping[str, object],
    parent_forecast_blob: bytes,
    child_forecast_blob: bytes,
    forecast_bundle: bytes,
    expected_bundle_sha256: str,
    request_der: bytes,
    response_der: bytes,
    tsa_trust_root_pem: bytes,
    expected_root_pem_sha256: str,
    tsa_untrusted_chain_pem: bytes,
    expected_signer_cert_sha256: str,
    expected_policy_oid: str,
    source_origin_hour_utc: int,
) -> dict[str, object]:
    """Bind the *exact* signed 4-row message to a claimed Git ledger append."""
    if (
        type(parent_forecast_blob) is not bytes
        or type(child_forecast_blob) is not bytes
        or type(forecast_bundle) is not bytes
        or not child_forecast_blob.startswith(parent_forecast_blob)
        or child_forecast_blob[len(parent_forecast_blob) :] != forecast_bundle
    ):
        raise ValueError("RFC3161 signed bundle differs from exact appended Git forecast bytes")

    proof = verify_future_only_rfc3161_seal(
        forecast_bundle=forecast_bundle,
        expected_bundle_sha256=expected_bundle_sha256,
        request_der=request_der,
        response_der=response_der,
        tsa_trust_root_pem=tsa_trust_root_pem,
        expected_root_pem_sha256=expected_root_pem_sha256,
        tsa_untrusted_chain_pem=tsa_untrusted_chain_pem,
        expected_signer_cert_sha256=expected_signer_cert_sha256,
        expected_policy_oid=expected_policy_oid,
        source_origin_hour_utc=source_origin_hour_utc,
    )
    rows = [json.loads(line) for line in forecast_bundle.splitlines()]
    projection = [{key: row[key] for key in _META} for row in rows]
    git = bind_supplied_git_commit_tree_chain(
        parent_commit,
        child_commit,
        parent_tree,
        child_tree,
        parent_forecast_blob,
        child_forecast_blob,
        projection,
    )
    eligible = proof["all_full_elapsed_horizons_eligible_against_signed_time"] is True
    return {
        "status": (
            "SIGNED_GIT_APPEND_MATCH_UNVERIFIED_EXTERNAL_PUBLICATION"
            if eligible
            else "SIGNED_GIT_APPEND_MATCH_BUT_ELAPSED_WINDOW_BLOCKED"
        ),
        "exact_signed_forecast_bytes_match_supplied_git_append": True,
        "four_horizon_rows_matched": git["byte_binding"]["appended_forecast_count"] == 4,
        "signed_elapsed_window_eligible": eligible,
        "claimed_child_commit_sha": git["claimed_child_commit_sha"],
        "signed_bundle_sha256": proof["forecast_bundle_sha256"],
        "git_blob_sha256": git["byte_binding"]["child_blob_sha256"],
        "github_data_independently_authenticated_by_this_function": False,
        "tsa_trust_independently_authorized_by_this_function": False,
        "independent_public_forecast_delivery_attested": False,
        "scientific_authorization": "NO_RUN",
    }
