"""Synthetic RFC3161 signed-time fixtures: no external provider or market data."""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
import scripts.stage6_rfc3161_seal as seal_module
from scripts.stage6_rfc3161_seal import verify_future_only_rfc3161_seal

POLICY = "1.3.6.1.4.1.57615.6.1"
SYNTHETIC = b'{"synthetic_forecast_bundle": "not_real_market_data"}\n'


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
    payload = tmp / "batch.txt"
    payload.write_bytes(SYNTHETIC)
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
        "bundle": SYNTHETIC,
        "sha": hashlib.sha256(SYNTHETIC).hexdigest(),
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
        origin_hour = int(source["signed_hour"]) - 3600
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
