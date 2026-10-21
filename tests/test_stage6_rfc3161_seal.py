"""Synthetic RFC3161 signed-time fixtures: no external provider or market data."""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from scripts.stage6_rfc3161_seal import verify_future_only_rfc3161_seal

POLICY = "1.3.6.1.4.1.57615.6.1"
SYNTHETIC = b'{"synthetic_forecast_bundle": "not_real_market_data"}\n'


def _call(*args: str) -> None:
    subprocess.run(  # noqa: S603,S607 - local synthetic OpenSSL test fixture, no shell.
        args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )


@pytest.fixture(scope="module")
def synthetic_tsa(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    if shutil.which("openssl") is None:
        pytest.fail("OpenSSL is required: never skip time-proof tests in CI")
    tmp: Path = tmp_path_factory.mktemp("mock_tsa")
    root_key, root = tmp / "root.key", tmp / "root.pem"
    tsa_key, tsa_csr, tsa = tmp / "tsa.key", tmp / "tsa.csr", tmp / "tsa.pem"
    _call(
        "openssl", "req", "-new", "-x509", "-newkey", "rsa:2048", "-nodes",
        "-days", "2", "-subj", "/CN=Stage6 Temporary Test Root",
        "-addext", "basicConstraints=critical,CA:TRUE",
        "-addext", "keyUsage=critical,keyCertSign,cRLSign",
        "-keyout", str(root_key), "-out", str(root),
    )
    _call(
        "openssl", "req", "-new", "-newkey", "rsa:2048", "-nodes",
        "-subj", "/CN=Stage6 Temporary Test TSA", "-keyout", str(tsa_key),
        "-out", str(tsa_csr),
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
        "openssl", "x509", "-req", "-in", str(tsa_csr), "-CA", str(root),
        "-CAkey", str(root_key), "-CAcreateserial", "-days", "2",
        "-extfile", str(extensions), "-out", str(tsa),
    )
    payload = tmp / "batch.txt"
    payload.write_bytes(SYNTHETIC)
    query, response = tmp / "query.tsq", tmp / "response.tsr"
    _call(
        "openssl", "ts", "-query", "-data", str(payload), "-sha256",
        "-cert", "-out", str(query),
    )
    _call(
        "openssl", "ts", "-reply", "-queryfile", str(query),
        "-signer", str(tsa), "-inkey", str(tsa_key), "-chain", str(root),
        "-tspolicy", POLICY, "-out", str(response),
    )
    display = subprocess.run(  # noqa: S603,S607 - local generated DER only.
        ["openssl", "ts", "-reply", "-in", str(response), "-text"],
        text=True, capture_output=True, check=True,
    ).stdout
    match = re.search(r"^Time stamp: (.+) GMT$", display, flags=re.MULTILINE)
    assert match is not None
    signed_time = datetime.strptime(match.group(1), "%b %d %H:%M:%S %Y").replace(
        tzinfo=UTC
    )
    root_bytes = root.read_bytes()
    return {
        "bundle": SYNTHETIC,
        "sha": hashlib.sha256(SYNTHETIC).hexdigest(),
        "query": query.read_bytes(),
        "response": response.read_bytes(),
        "root": root_bytes,
        "root_sha": hashlib.sha256(root_bytes).hexdigest(),
        "tsa": tsa.read_bytes(),
        "signed_hour": int(signed_time.timestamp()) // 3600 * 3600,
    }


def kwargs(source: dict[str, object], *, origin_hour: int | None = None) -> dict[str, object]:
    if origin_hour is None:
        origin_hour = int(source["signed_hour"]) - 3600
    return {
        "forecast_bundle": source["bundle"],
        "expected_bundle_sha256": source["sha"],
        "request_der": source["query"],
        "response_der": source["response"],
        "tsa_trust_root_pem": source["root"],
        "expected_root_pem_sha256": source["root_sha"],
        "tsa_untrusted_chain_pem": source["tsa"],
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


def test_signed_synthetic_rfc3161_blocks_old_origin_even_when_signature_valid(synthetic_tsa):
    origin = int(synthetic_tsa["signed_hour"]) - 12 * 3600
    ev = verify_future_only_rfc3161_seal(**kwargs(synthetic_tsa, origin_hour=origin))
    assert ev["status"] == "CONFIGURED_TSA_SIGNED_BUT_OUTSIDE_PREDECLARED_WINDOW"
    assert ev["all_full_elapsed_horizons_eligible_against_signed_time"] is False
    assert ev["horizons"][0]["signed_minimum_elapsed_eligible"] is False


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
        "openssl", "ts", "-query", "-data", str(payload), "-sha256", "-cert",
        "-out", str(alternative_query),
    )
    p = kwargs(synthetic_tsa)
    p["request_der"] = alternative_query.read_bytes()
    with pytest.raises(ValueError, match="signature, nonce, content or chain"):
        verify_future_only_rfc3161_seal(**p)
