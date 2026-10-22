"""Synthetic RFC3161 signed-time fixtures: no external provider or market data."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import scripts.stage6_rfc3161_seal as seal_module
from scripts.stage6_rfc3161_git_crosscheck import crosscheck_signed_forecast_git_append
from scripts.stage6_rfc3161_seal import verify_future_only_rfc3161_seal

POLICY = "1.3.6.1.4.1.57615.6.1"


def _fixture_time_boundary_delay(seconds_into_hour: float) -> float:
    """Avoid midnight/hour-edge races in second-resolution mock TSA genTime."""
    if not 0 <= seconds_into_hour < 3600:
        raise ValueError("Seconds into hour must be in the canonical range")
    if seconds_into_hour < 5:
        return 5.25 - seconds_into_hour
    if seconds_into_hour >= 3590:
        return 3605.25 - seconds_into_hour
    return 0.0


def _safe_mock_origin() -> int:
    """Choose a completed candle only inside the current hour's safe window."""
    while True:
        now = datetime.now(UTC).timestamp()
        delay = _fixture_time_boundary_delay(now % 3600)
        if delay == 0:
            return int(now) // 3600 * 3600 - 3600
        time.sleep(delay)


def _mock_future_forecast_bundle(origin_hour: int) -> bytes:
    source = datetime.fromtimestamp(origin_hour, tz=UTC)
    issued = (source + timedelta(hours=1, microseconds=1)).isoformat()
    rows = []
    for horizon in (1, 4, 12, 24):
        rows.append(
            {
                "version": "stage6-hourly-full-elapsed-v1-research-only",
                "issued_at_utc": issued,
                "origin_hour_utc": source.isoformat(),
                "target_hour_utc": (source + timedelta(hours=horizon + 1)).isoformat(),
                "target_close_utc": (source + timedelta(hours=horizon + 2)).isoformat(),
                "horizon_hours": horizon,
                "origin_close_usd": 10.0,
                "forecast_usd": 11.0,
                "persistence_usd": 10.0,
                "observed_volatility_hourly": 0.1,
                "training_hours": 720,
                "resolved_training_examples": 500,
                "holdout_selected_blend": 0.25,
                "source": "coinbase:exchange:BTC-USD:1h:close",
                "research_only": True,
            }
        )
    return "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows).encode()


def _call(*args: str) -> None:
    subprocess.run(  # noqa: S603 - local synthetic OpenSSL test fixture, no shell.
        args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )


@pytest.fixture(scope="module")
def synthetic_tsa(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    openssl_path = shutil.which("openssl")
    if openssl_path is None:
        pytest.fail("OpenSSL is required: never skip time-proof tests in CI")
    tmp: Path = tmp_path_factory.mktemp("mock_tsa")
    root_key, root = tmp / "root.key", tmp / "root.pem"
    tsa_key, tsa_csr, tsa = tmp / "tsa.key", tmp / "tsa.csr", tmp / "tsa.pem"
    _call(
        "openssl",
        "req",
        "-new",
        "-x509",
        "-newkey",
        "rsa:2048",
        "-nodes",
        "-days",
        "2",
        "-subj",
        "/CN=Stage6 Temporary Test Root",
        "-addext",
        "basicConstraints=critical,CA:TRUE",
        "-addext",
        "keyUsage=critical,keyCertSign,cRLSign",
        "-keyout",
        str(root_key),
        "-out",
        str(root),
    )
    _call(
        "openssl",
        "req",
        "-new",
        "-newkey",
        "rsa:2048",
        "-nodes",
        "-subj",
        "/CN=Stage6 Temporary Test TSA",
        "-keyout",
        str(tsa_key),
        "-out",
        str(tsa_csr),
    )
    extensions = tmp / "tsa.ext"
    extensions.write_text(
        "basicConstraints=critical,CA:FALSE\n"
        "keyUsage=critical,digitalSignature,nonRepudiation\n"
        "extendedKeyUsage=critical,timeStamping\n"
        "subjectKeyIdentifier=hash\n"
        "authorityKeyIdentifier=keyid,issuer\n"
    )
    _call(
        "openssl",
        "x509",
        "-req",
        "-in",
        str(tsa_csr),
        "-CA",
        str(root),
        "-CAkey",
        str(root_key),
        "-CAcreateserial",
        "-days",
        "2",
        "-extfile",
        str(extensions),
        "-out",
        str(tsa),
    )
    # Ensures token genTime with second precision is strictly AFTER signed issuance.
    origin_hour = _safe_mock_origin()
    synthetic_bundle = _mock_future_forecast_bundle(origin_hour)
    payload = tmp / "batch.txt"
    payload.write_bytes(synthetic_bundle)
    query, response = tmp / "query.tsq", tmp / "response.tsr"
    _call(
        "openssl",
        "ts",
        "-query",
        "-data",
        str(payload),
        "-sha256",
        "-cert",
        "-out",
        str(query),
    )
    _call(
        "openssl",
        "ts",
        "-reply",
        "-queryfile",
        str(query),
        "-signer",
        str(tsa),
        "-inkey",
        str(tsa_key),
        "-chain",
        str(root),
        "-tspolicy",
        POLICY,
        "-out",
        str(response),
    )
    display = subprocess.run(  # noqa: S603 - local generated DER only.
        [openssl_path, "ts", "-reply", "-in", str(response), "-text"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    match = re.search(r"^Time stamp: (.+) GMT$", display, flags=re.MULTILINE)
    assert match is not None
    signed_time = datetime.strptime(match.group(1), "%b %d %H:%M:%S %Y").replace(tzinfo=UTC)
    root_bytes = root.read_bytes()
    signer_der = subprocess.run(  # noqa: S603 - test-only OpenSSL certificate.
        [openssl_path, "x509", "-in", str(tsa), "-outform", "DER"],
        check=True,
        capture_output=True,
    ).stdout
    return {
        "bundle": synthetic_bundle,
        "sha": hashlib.sha256(synthetic_bundle).hexdigest(),
        "origin_hour": origin_hour,
        "signer_cert_path": tsa,
        "signer_key_path": tsa_key,
        "query": query.read_bytes(),
        "response": response.read_bytes(),
        "root": root_bytes,
        "root_sha": hashlib.sha256(root_bytes).hexdigest(),
        "tsa": tsa.read_bytes(),
        "tsa_cert_sha256": hashlib.sha256(signer_der).hexdigest(),
        "root_certificate_path": root,
        "root_private_key_path": root_key,
        "extensions_path": extensions,
        "signed_time_epoch": int(signed_time.timestamp()),
        "signed_hour": int(signed_time.timestamp()) // 3600 * 3600,
    }


def kwargs(source: dict[str, object], *, origin_hour: int | None = None) -> dict[str, object]:
    if origin_hour is None:
        origin_hour = int(source["origin_hour"])
    return {
        "forecast_bundle": source["bundle"],
        "expected_bundle_sha256": source["sha"],
        "request_der": source["query"],
        "response_der": source["response"],
        "tsa_trust_root_pem": source["root"],
        "expected_root_pem_sha256": source["root_sha"],
        "tsa_untrusted_chain_pem": source["tsa"],
        "expected_signer_cert_sha256": source["tsa_cert_sha256"],
        "expected_policy_oid": POLICY,
        "source_origin_hour_utc": origin_hour,
    }


def test_signed_synthetic_rfc3161_verifies_bundle_and_future_targets(synthetic_tsa):
    evidence = verify_future_only_rfc3161_seal(**kwargs(synthetic_tsa))
    assert evidence["rfc3161_signature_nonce_imprint_and_configured_chain_verified"] is True
    assert evidence["status"] == "CONFIGURED_TSA_SIGNED_PREDEADLINE_BUNDLE_UNVERIFIED_CUSTODY"
    assert evidence["all_full_elapsed_horizons_eligible_against_signed_time"] is True
    assert [x["training_target_row_shift"] for x in evidence["horizons"]] == [2, 5, 13, 25]
    assert evidence["trust_root_independently_preapproved_by_this_function"] is False
    assert evidence["public_forecast_availability_independently_proven"] is False
    assert evidence["scientific_authorization"] == "NO_RUN"


def test_signed_token_cannot_relabel_old_origin_as_new(synthetic_tsa):
    wrong_origin = int(synthetic_tsa["origin_hour"]) - 12 * 3600
    with pytest.raises(ValueError, match="origin differs"):
        verify_future_only_rfc3161_seal(**kwargs(synthetic_tsa, origin_hour=wrong_origin))


def test_tampered_payload_with_original_declared_sha_rejected(synthetic_tsa):
    p = kwargs(synthetic_tsa)
    p["forecast_bundle"] = b"changed bytes" + p["forecast_bundle"]
    with pytest.raises(ValueError, match="predeclared SHA256"):
        verify_future_only_rfc3161_seal(**p)


def test_rehashed_wrong_payload_rejected_by_actual_token_imprint(synthetic_tsa):
    p = kwargs(synthetic_tsa)
    p["forecast_bundle"] = b"changed bytes" + p["forecast_bundle"]
    p["expected_bundle_sha256"] = hashlib.sha256(p["forecast_bundle"]).hexdigest()
    with pytest.raises(ValueError, match="signature, nonce, content or chain"):
        verify_future_only_rfc3161_seal(**p)


def test_forged_root_bytes_do_not_match_predeclared_root_sha(synthetic_tsa):
    p = kwargs(synthetic_tsa)
    p["tsa_trust_root_pem"] += b"\n"
    with pytest.raises(ValueError, match="pinned digest"):
        verify_future_only_rfc3161_seal(**p)


def test_wrong_policy_oid_rejected(synthetic_tsa):
    p = kwargs(synthetic_tsa)
    p["expected_policy_oid"] = "1.3.6.1.4.1.57615.6.2"
    with pytest.raises(ValueError, match="predeclared policy"):
        verify_future_only_rfc3161_seal(**p)


def test_wrong_origin_must_be_hour_aligned(synthetic_tsa):
    p = kwargs(synthetic_tsa)
    p["source_origin_hour_utc"] += 1
    with pytest.raises(ValueError, match="hour-aligned"):
        verify_future_only_rfc3161_seal(**p)


def test_different_valid_query_nonce_does_not_verify(synthetic_tsa, tmp_path: Path):
    payload = tmp_path / "payload"
    payload.write_bytes(synthetic_tsa["bundle"])
    alternative_query = tmp_path / "different_nonce.tsq"
    _call(
        "openssl",
        "ts",
        "-query",
        "-data",
        str(payload),
        "-sha256",
        "-cert",
        "-out",
        str(alternative_query),
    )
    p = kwargs(synthetic_tsa)
    p["request_der"] = alternative_query.read_bytes()
    with pytest.raises(ValueError, match="signature, nonce, content or chain"):
        verify_future_only_rfc3161_seal(**p)


def test_wrong_signer_certificate_fingerprint_blocks(synthetic_tsa):
    params = kwargs(synthetic_tsa)
    params["expected_signer_cert_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="unpinned TSA certificate"):
        verify_future_only_rfc3161_seal(**params)


def test_different_signer_under_same_root_rejected(synthetic_tsa, tmp_path: Path):
    other_key = tmp_path / "other.key"
    other_csr = tmp_path / "other.csr"
    other_cert = tmp_path / "other.pem"
    _call(
        "openssl",
        "req",
        "-new",
        "-newkey",
        "rsa:2048",
        "-nodes",
        "-subj",
        "/CN=Unapproved Timestamp Leaf",
        "-keyout",
        str(other_key),
        "-out",
        str(other_csr),
    )
    _call(
        "openssl",
        "x509",
        "-req",
        "-in",
        str(other_csr),
        "-CA",
        str(synthetic_tsa["root_certificate_path"]),
        "-CAkey",
        str(synthetic_tsa["root_private_key_path"]),
        "-CAcreateserial",
        "-days",
        "2",
        "-extfile",
        str(synthetic_tsa["extensions_path"]),
        "-out",
        str(other_cert),
    )
    old_query = tmp_path / "same_query.tsq"
    old_query.write_bytes(synthetic_tsa["query"])
    alternate = tmp_path / "alternate_response.tsr"
    _call(
        "openssl",
        "ts",
        "-reply",
        "-queryfile",
        str(old_query),
        "-signer",
        str(other_cert),
        "-inkey",
        str(other_key),
        "-chain",
        str(synthetic_tsa["root_certificate_path"]),
        "-tspolicy",
        POLICY,
        "-out",
        str(alternate),
    )
    params = kwargs(synthetic_tsa)
    params["response_der"] = alternate.read_bytes()
    with pytest.raises(ValueError, match="unpinned TSA certificate"):
        verify_future_only_rfc3161_seal(**params)


def test_certificate_chain_is_checked_at_signed_token_time(synthetic_tsa, monkeypatch):
    seen: list[int] = []
    original = seal_module._openssl

    def observing_openssl(openssl_path: str, *args: str) -> str:
        if args[:2] == ("ts", "-verify"):
            idx = args.index("-attime")
            seen.append(int(args[idx + 1]))
        return original(openssl_path, *args)

    monkeypatch.setattr(seal_module, "_openssl", observing_openssl)
    value = verify_future_only_rfc3161_seal(**kwargs(synthetic_tsa))
    assert value["tsa_signer_cert_validity_checked_at_signed_time"] is True
    assert seen == [int(synthetic_tsa["signed_time_epoch"])] * 2


def _resign_mock_bundle(
    source: dict[str, object], tmp_path: Path, forecast_bundle: bytes
) -> tuple[bytes, bytes]:
    path = tmp_path / "signed_forecasts.jsonl"
    path.write_bytes(forecast_bundle)
    query = tmp_path / "new_query.tsq"
    reply = tmp_path / "new_response.tsr"
    _call(
        "openssl",
        "ts",
        "-query",
        "-data",
        str(path),
        "-sha256",
        "-cert",
        "-out",
        str(query),
    )
    _call(
        "openssl",
        "ts",
        "-reply",
        "-queryfile",
        str(query),
        "-signer",
        str(source["signer_cert_path"]),
        "-inkey",
        str(source["signer_key_path"]),
        "-chain",
        str(source["root_certificate_path"]),
        "-tspolicy",
        POLICY,
        "-out",
        str(reply),
    )
    return query.read_bytes(), reply.read_bytes()


def test_signed_but_truly_old_forecast_origin_is_blocked(synthetic_tsa, tmp_path: Path):
    past_origin = int(synthetic_tsa["origin_hour"]) - 12 * 3600
    old_bundle = _mock_future_forecast_bundle(past_origin)
    query, response = _resign_mock_bundle(synthetic_tsa, tmp_path, old_bundle)
    params = kwargs(synthetic_tsa, origin_hour=past_origin)
    params["forecast_bundle"] = old_bundle
    params["expected_bundle_sha256"] = hashlib.sha256(old_bundle).hexdigest()
    params["request_der"] = query
    params["response_der"] = response
    result = verify_future_only_rfc3161_seal(**params)
    assert result["status"] == "CONFIGURED_TSA_SIGNED_BUT_OUTSIDE_PREDECLARED_WINDOW"
    assert result["all_full_elapsed_horizons_eligible_against_signed_time"] is False


def test_signed_wrong_target_close_cannot_pass_even_when_root_and_signer_valid(
    synthetic_tsa, tmp_path: Path
):
    source_origin = int(synthetic_tsa["origin_hour"])
    rows = [
        json.loads(line)
        for line in _mock_future_forecast_bundle(source_origin).decode().splitlines()
    ]
    rows[0]["target_close_utc"] = rows[1]["target_close_utc"]
    wrong_bundle = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows).encode()
    query, response = _resign_mock_bundle(synthetic_tsa, tmp_path, wrong_bundle)
    params = kwargs(synthetic_tsa)
    params["forecast_bundle"] = wrong_bundle
    params["expected_bundle_sha256"] = hashlib.sha256(wrong_bundle).hexdigest()
    params["request_der"] = query
    params["response_der"] = response
    with pytest.raises(ValueError, match="target close does not match"):
        verify_future_only_rfc3161_seal(**params)


def test_duplicate_signed_origin_metadata_key_rejected(synthetic_tsa, tmp_path: Path):
    origin = int(synthetic_tsa["origin_hour"])
    bundle = _mock_future_forecast_bundle(origin)
    replaced = bundle.replace(
        b'"origin_hour_utc": ',
        b'"origin_hour_utc": "forged", "origin_hour_utc": ',
        1,
    )
    query, response = _resign_mock_bundle(synthetic_tsa, tmp_path, replaced)
    params = kwargs(synthetic_tsa)
    params["forecast_bundle"] = replaced
    params["expected_bundle_sha256"] = hashlib.sha256(replaced).hexdigest()
    params["request_der"] = query
    params["response_der"] = response
    with pytest.raises(ValueError, match="Duplicate key"):
        verify_future_only_rfc3161_seal(**params)


def test_rfc3161_accuracy_upper_bound_blocks_near_deadline():
    from scripts.stage6_rfc3161_seal import (
        _is_minimum_elapsed_eligible,
        _signed_accuracy_ns,
    )

    # OpenSSL prints this exact hex-based accuracy format.
    text = "Accuracy: 0x01 seconds, 0x01F4 millis, 0x64 micros"
    error_ns = _signed_accuracy_ns(text)
    assert error_ns == 1_500_100_000
    close = 1_000_000_000_000
    deadline = close + 2 * 3600 * 1_000_000_000
    nominal = deadline - 3600 * 1_000_000_000 - 500_000_000
    assert not _is_minimum_elapsed_eligible(
        source_close_ns=close,
        target_close_ns=deadline,
        horizon_hours=1,
        signed_time_lower_ns=nominal - error_ns,
        signed_time_upper_ns=nominal + error_ns,
    )
    assert _is_minimum_elapsed_eligible(
        source_close_ns=close,
        target_close_ns=deadline,
        horizon_hours=1,
        signed_time_lower_ns=nominal - 1,
        signed_time_upper_ns=nominal,
    )


@pytest.mark.parametrize(
    "accuracy_text",
    ["Accuracy: unspecified", "", "Accuracy: 0x0A micros, 0x01 micros"],
)
def test_unestablished_or_malformed_accuracy_is_not_accepted(accuracy_text):
    from scripts.stage6_rfc3161_seal import _signed_accuracy_ns

    with pytest.raises(ValueError, match="accuracy"):
        _signed_accuracy_ns(accuracy_text)


def test_real_synthetic_signed_token_accuracy_is_applied(synthetic_tsa):
    evidence = verify_future_only_rfc3161_seal(**kwargs(synthetic_tsa))
    assert evidence["tsa_signed_accuracy_ns"] > 0
    assert evidence["tsa_signed_utc_time_upper_ns"] == (
        evidence["tsa_signed_utc_time_ns"] + evidence["tsa_signed_accuracy_ns"]
    )
    first = evidence["horizons"][0]
    assert first["conservative_signed_elapsed_lead_ns"] == (
        first["target_close_utc"] * 1_000_000_000 - evidence["tsa_signed_utc_time_upper_ns"]
    )


@pytest.mark.parametrize(
    ("bad_field", "bad_value"),
    [
        ("forecast_usd", None),
        ("forecast_usd", False),
        ("origin_close_usd", -1),
        ("persistence_usd", "10"),
        ("observed_volatility_hourly", -1),
        ("training_hours", False),
        ("resolved_training_examples", 0),
        ("holdout_selected_blend", 2),
    ],
)
def test_correctly_signed_invalid_numeric_forecast_is_rejected(
    synthetic_tsa, tmp_path: Path, bad_field, bad_value
):
    bundle = _mock_future_forecast_bundle(int(synthetic_tsa["origin_hour"]))
    rows = [json.loads(line) for line in bundle.decode().splitlines()]
    rows[0][bad_field] = bad_value
    changed = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows).encode()
    query, response = _resign_mock_bundle(synthetic_tsa, tmp_path, changed)
    params = kwargs(synthetic_tsa)
    params.update(
        forecast_bundle=changed,
        expected_bundle_sha256=hashlib.sha256(changed).hexdigest(),
        request_der=query,
        response_der=response,
    )
    with pytest.raises(ValueError, match="Signed"):
        verify_future_only_rfc3161_seal(**params)


def test_overflowing_json_exponent_in_signed_forecast_rejected(synthetic_tsa, tmp_path):
    original = _mock_future_forecast_bundle(int(synthetic_tsa["origin_hour"]))
    changed = original.replace(b'"forecast_usd": 11.0', b'"forecast_usd": 1e400', 1)
    assert changed != original
    query, response = _resign_mock_bundle(synthetic_tsa, tmp_path, changed)
    params = kwargs(synthetic_tsa)
    params.update(
        forecast_bundle=changed,
        expected_bundle_sha256=hashlib.sha256(changed).hexdigest(),
        request_der=query,
        response_der=response,
    )
    with pytest.raises(ValueError, match="finite positive"):
        verify_future_only_rfc3161_seal(**params)


def test_issuance_equal_to_source_candle_close_rejected(synthetic_tsa, tmp_path):
    origin = int(synthetic_tsa["origin_hour"])
    bundle = _mock_future_forecast_bundle(origin)
    rows = [json.loads(line) for line in bundle.decode().splitlines()]
    exact_close = datetime.fromtimestamp(origin + 3600, tz=UTC).isoformat()
    for row in rows:
        row["issued_at_utc"] = exact_close
    changed = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows).encode()
    query, response = _resign_mock_bundle(synthetic_tsa, tmp_path, changed)
    params = kwargs(synthetic_tsa)
    params.update(
        forecast_bundle=changed,
        expected_bundle_sha256=hashlib.sha256(changed).hexdigest(),
        request_der=query,
        response_der=response,
    )
    with pytest.raises(ValueError, match="outside source-close-to-token"):
        verify_future_only_rfc3161_seal(**params)


def _mock_git_chain_for_signed_bundle(synthetic_tsa):
    parent = b'{"older_forecasts":"opaque"}\n'
    child = parent + synthetic_tsa["bundle"]

    def git_sha(data):
        return hashlib.sha1(
            b"blob " + str(len(data)).encode() + b"\0" + data,
            usedforsecurity=False,
        ).hexdigest()

    parent_commit_sha, child_commit_sha = "a" * 40, "b" * 40
    parent_tree_sha, child_tree_sha = "c" * 40, "d" * 40
    return {
        **kwargs(synthetic_tsa),
        "parent_forecast_blob": parent,
        "child_forecast_blob": child,
        "parent_commit": {"sha": parent_commit_sha, "tree_sha": parent_tree_sha},
        "child_commit": {
            "sha": child_commit_sha,
            "tree_sha": child_tree_sha,
            "parents": [parent_commit_sha],
            "changed_paths": ["research/hourly_forecasts.jsonl"],
        },
        "parent_tree": {
            "sha": parent_tree_sha,
            "truncated": False,
            "entries": [
                {
                    "path": "research/hourly_forecasts.jsonl",
                    "type": "blob",
                    "mode": "100644",
                    "sha": git_sha(parent),
                }
            ],
        },
        "child_tree": {
            "sha": child_tree_sha,
            "truncated": False,
            "entries": [
                {
                    "path": "research/hourly_forecasts.jsonl",
                    "type": "blob",
                    "mode": "100644",
                    "sha": git_sha(child),
                }
            ],
        },
    }


def test_signed_tsa_bytes_must_match_exact_git_append(synthetic_tsa):
    verified = crosscheck_signed_forecast_git_append(
        **_mock_git_chain_for_signed_bundle(synthetic_tsa)
    )
    assert verified["exact_signed_forecast_bytes_match_supplied_git_append"] is True
    assert verified["four_horizon_rows_matched"] is True
    assert verified["signed_elapsed_window_eligible"] is True
    assert verified["github_data_independently_authenticated_by_this_function"] is False
    assert verified["independent_public_forecast_delivery_attested"] is False
    assert verified["scientific_authorization"] == "NO_RUN"


def test_same_valid_tsa_token_cannot_attest_different_committed_forecast(synthetic_tsa):
    kwargs_git = _mock_git_chain_for_signed_bundle(synthetic_tsa)
    kwargs_git["child_forecast_blob"] = kwargs_git["child_forecast_blob"].replace(
        b'"forecast_usd": 11.0',
        b'"forecast_usd": 11.7',
    )
    with pytest.raises(ValueError, match="signed bundle differs"):
        crosscheck_signed_forecast_git_append(**kwargs_git)


def test_signed_forecast_does_not_accept_false_git_tree_blob_id(synthetic_tsa):
    kwargs_git = _mock_git_chain_for_signed_bundle(synthetic_tsa)
    kwargs_git["child_tree"]["entries"][0]["sha"] = "f" * 40
    with pytest.raises(ValueError, match="Child Git blob SHA"):
        crosscheck_signed_forecast_git_append(**kwargs_git)


def test_stale_but_signed_git_append_remains_ineligible(synthetic_tsa, tmp_path):
    old_origin = int(synthetic_tsa["origin_hour"]) - 12 * 3600
    old_bundle = _mock_future_forecast_bundle(old_origin)
    query, response = _resign_mock_bundle(synthetic_tsa, tmp_path, old_bundle)
    args = _mock_git_chain_for_signed_bundle(synthetic_tsa)
    parent = args["parent_forecast_blob"]
    child = parent + old_bundle
    args["forecast_bundle"] = old_bundle
    args["child_forecast_blob"] = child
    args["source_origin_hour_utc"] = old_origin
    args["expected_bundle_sha256"] = hashlib.sha256(old_bundle).hexdigest()
    args["request_der"] = query
    args["response_der"] = response
    args["child_tree"]["entries"][0]["sha"] = hashlib.sha1(
        b"blob " + str(len(child)).encode() + b"\0" + child,
        usedforsecurity=False,
    ).hexdigest()
    verified = crosscheck_signed_forecast_git_append(**args)
    assert verified["exact_signed_forecast_bytes_match_supplied_git_append"] is True
    assert verified["signed_elapsed_window_eligible"] is False
    assert verified["scientific_authorization"] == "NO_RUN"


@pytest.mark.parametrize(
    ("second_offset", "expected_wait"),
    [
        (0.0, 5.25),
        (0.000001, 5.249999),
        (4.999, 0.251),
        (5.0, 0.0),
        (120.0, 0.0),
        (3589.999, 0.0),
        (3590.0, 15.25),
        (3599.999, 5.251),
    ],
)
def test_mock_tsa_hour_edge_selection_is_bounded_and_deterministic(second_offset, expected_wait):
    delay = _fixture_time_boundary_delay(second_offset)
    assert delay == pytest.approx(expected_wait, abs=1e-5)
    safe_offset = (second_offset + delay) % 3600
    assert 5 <= safe_offset < 3590


def test_real_mock_issue_precedes_token_gen_time_in_full_hour_safe_window(synthetic_tsa):
    rows = [json.loads(line) for line in synthetic_tsa["bundle"].decode().splitlines()]
    issued_at = datetime.fromisoformat(rows[0]["issued_at_utc"]).timestamp()
    assert issued_at > int(synthetic_tsa["origin_hour"]) + 3600
    assert issued_at < float(synthetic_tsa["signed_time_epoch"])
