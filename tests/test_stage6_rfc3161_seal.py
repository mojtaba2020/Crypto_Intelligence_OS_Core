"""Synthetic RFC3161 signed-time fixtures: no external provider or market data."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import scripts.stage6_rfc3161_seal as seal_module
from scripts.stage6_rfc3161_seal import verify_future_only_rfc3161_seal

POLICY = "1.3.6.1.4.1.57615.6.1"
def _mock_future_forecast_bundle(origin_hour: int) -> bytes:
    source = datetime.fromtimestamp(origin_hour, tz=UTC)
    issued = (source + timedelta(hours=1)).isoformat()
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
    origin_hour = int(datetime.now(UTC).timestamp()) // 3600 * 3600 - 3600
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
        "openssl", "ts", "-query", "-data", str(path), "-sha256",
        "-cert", "-out", str(query),
    )
    _call(
        "openssl", "ts", "-reply", "-queryfile", str(query),
        "-signer", str(source["signer_cert_path"]),
        "-inkey", str(source["signer_key_path"]),
        "-chain", str(source["root_certificate_path"]),
        "-tspolicy", POLICY, "-out", str(reply),
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
        b'"origin_hour_utc": ', b'"origin_hour_utc": "forged", "origin_hour_utc": ',
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
