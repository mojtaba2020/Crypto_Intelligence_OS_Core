"""Offline RFC3161 evidence verifier for a future-only, versioned Stage-6 lane.

No network, no certificate/secret generation, no market data processing and no
scientific promotion. The TSA trust root MUST be approved and pinned outside
this module before meaningful independent attestation is claimed.
"""

from __future__ import annotations

import calendar
import hashlib
import hmac
import os
import re
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

HORIZONS_HOURS = (1, 4, 12, 24)
MAX_BUNDLE_BYTES = 1_000_000
MAX_DER_BYTES = 200_000
MAX_PEM_BYTES = 200_000
SECOND_NS = 1_000_000_000
HOUR_NS = 3600 * SECOND_NS
POLICY_OID = re.compile(r"^[0-2](?:\.(?:0|[1-9]\d*)){2,18}$")
SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
STAMP_RE = re.compile(
    r"^Time stamp: (?P<date>[A-Z][a-z]{2} +\d{1,2} +\d{2}:\d{2}:\d{2} +\d{4})"
    r"(?P<subseconds>\.\d{1,9})? GMT$",
    re.MULTILINE,
)


def _verified_input(value: object, *, name: str, limit: int) -> bytes:
    if type(value) is not bytes or not 0 < len(value) <= limit:
        raise ValueError(f"{name} must be nonempty, bounded exact bytes")
    return value


def _openssl(openssl_path: str, *arguments: str) -> str:
    # Internal fixed subcommands, no shell, no networking or external API.
    env = {**os.environ, "LC_ALL": "C"}
    try:
        completed = subprocess.run(  # noqa: S603 - bounded local OpenSSL command.
            [openssl_path, *arguments],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("Local OpenSSL verifier unavailable") from exc
    if completed.returncode:
        # Avoid emitting potentially sensitive paths, data or OpenSSL stderr.
        raise ValueError("RFC3161 signature, nonce, content or chain verification failed")
    return completed.stdout


def _stamp_ns(text: str) -> int:
    found = STAMP_RE.findall(text)
    if len(found) != 1:
        raise ValueError("Exactly one signed RFC3161 timestamp is required")
    human_date, fraction = found[0]
    try:
        stamp = datetime.strptime(human_date, "%b %d %H:%M:%S %Y").replace(tzinfo=UTC)
    except ValueError as exc:
        raise ValueError("Invalid signed UTC timestamp") from exc
    nanos = int(fraction[1:].ljust(9, "0")) if fraction else 0
    return calendar.timegm(stamp.timetuple()) * SECOND_NS + nanos


def verify_future_only_rfc3161_seal(
    *,
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
    """Verify a TSA-signed timestamp against exact bytes and new target calendar.

    A passing local signature says the *configured* TSA signed an imprint of
    these bytes at genTime. It cannot itself authenticate the trust-root
    provisioning, public GitHub visibility, certificate revocation, or the
    forecast's committed Git append; these are separate scientific gates.
    """
    bundle = _verified_input(forecast_bundle, name="Forecast bundle", limit=MAX_BUNDLE_BYTES)
    query = _verified_input(request_der, name="RFC3161 query", limit=MAX_DER_BYTES)
    response = _verified_input(response_der, name="RFC3161 reply", limit=MAX_DER_BYTES)
    root = _verified_input(tsa_trust_root_pem, name="Trust root", limit=MAX_PEM_BYTES)
    signer = _verified_input(tsa_untrusted_chain_pem, name="TSA signer", limit=MAX_PEM_BYTES)
    if type(expected_bundle_sha256) is not str or not SHA256_HEX.fullmatch(expected_bundle_sha256):
        raise ValueError("A predeclared SHA256 forecast bundle digest is required")
    if not hmac.compare_digest(hashlib.sha256(bundle).hexdigest(), expected_bundle_sha256):
        raise ValueError("Forecast bundle differs from the predeclared SHA256 digest")
    if type(expected_root_pem_sha256) is not str or not SHA256_HEX.fullmatch(
        expected_root_pem_sha256
    ):
        raise ValueError("A predeclared TSA trust-root SHA256 is required")
    if not hmac.compare_digest(hashlib.sha256(root).hexdigest(), expected_root_pem_sha256):
        raise ValueError("TSA trust-root material differs from the pinned digest")
    if (
        type(expected_signer_cert_sha256) is not str
        or not SHA256_HEX.fullmatch(expected_signer_cert_sha256)
    ):
        raise ValueError("A predeclared TSA signing certificate fingerprint is required")
    if type(expected_policy_oid) is not str or not POLICY_OID.fullmatch(expected_policy_oid):
        raise ValueError("An exact predeclared TSA policy OID is required")
    if (
        type(source_origin_hour_utc) is not int
        or source_origin_hour_utc <= 0
        or source_origin_hour_utc >= 10**11
        or source_origin_hour_utc % 3600
    ):
        raise ValueError("A fixed hour-aligned UTC source origin is required")
    openssl_path = shutil.which("openssl")
    if openssl_path is None or not Path(openssl_path).is_absolute():
        raise ValueError("Local OpenSSL executable unavailable")

    with tempfile.TemporaryDirectory(prefix="stage6_rfc3161_") as directory:
        temp = Path(directory)
        files = {
            "payload": bundle,
            "query": query,
            "response": response,
            "root": root,
            "untrusted": signer,
        }
        for filename, content in files.items():
            (temp / filename).write_bytes(content)
        reply_text = _openssl(openssl_path, "ts", "-reply", "-in", str(temp / "response"), "-text")
        # Unverified genTime is used *only* to select verification epoch.
        stamp_ns = _stamp_ns(reply_text)
        epoch_floor = stamp_ns // SECOND_NS
        epoch_ceil = (stamp_ns + SECOND_NS - 1) // SECOND_NS
        _openssl(
            openssl_path, "ts", "-reply", "-in", str(temp / "response"),
            "-token_out", "-out", str(temp / "token.der"),
        )
        _openssl(
            openssl_path, "cms", "-verify", "-inform", "DER",
            "-in", str(temp / "token.der"), "-noverify", "-binary",
            "-signer", str(temp / "actual_signer.pem"),
            "-out", str(temp / "verified_tstinfo.der"),
        )
        signer_bytes = (temp / "actual_signer.pem").read_bytes()
        if signer_bytes.count(b"-----BEGIN CERTIFICATE-----") != 1:
            raise ValueError("RFC3161 token must contain exactly one CMS signer")
        fingerprint_line = _openssl(
            openssl_path, "x509", "-in", str(temp / "actual_signer.pem"),
            "-noout", "-fingerprint", "-sha256",
        ).strip()
        label, separator, fingerprint = fingerprint_line.partition("=")
        observed = fingerprint.replace(":", "").lower()
        if (
            separator != "="
            or label.lower() != "sha256 fingerprint"
            or not SHA256_HEX.fullmatch(observed)
            or not hmac.compare_digest(observed, expected_signer_cert_sha256)
        ):
            raise ValueError("RFC3161 token signed by unpinned TSA certificate")
        base_args = (
            "-in",
            str(temp / "response"),
            "-CAfile",
            str(temp / "root"),
            "-untrusted",
            str(temp / "untrusted"),
        )
        # The signer must validate at the TSA's own signed time, not "now".
        # Check both adjacent whole seconds for fractional genTime.
        for epoch in sorted({epoch_floor, epoch_ceil}):
            timed_args = (*base_args, "-attime", str(epoch))
            _openssl(
                openssl_path, "ts", "-verify", *timed_args,
                "-queryfile", str(temp / "query"),
            )
            _openssl(
                openssl_path, "ts", "-verify", *timed_args,
                "-data", str(temp / "payload"),
            )
        request_text = _openssl(openssl_path, "ts", "-query", "-in", str(temp / "query"), "-text")

    if len(re.findall(r"^Hash Algorithm: sha256$", request_text, re.MULTILINE)) != 1:
        raise ValueError("RFC3161 timestamp request must use SHA256")
    if len(re.findall(r"^Hash Algorithm: sha256$", reply_text, re.MULTILINE)) != 1:
        raise ValueError("RFC3161 TSA reply must use SHA256")
    if not re.search(r"^Nonce: 0x[0-9A-Fa-f]+$", request_text, re.MULTILINE):
        raise ValueError("RFC3161 request must contain unpredictable nonce")
    if not re.search(r"^Nonce: 0x[0-9A-Fa-f]+$", reply_text, re.MULTILINE):
        raise ValueError("RFC3161 token must contain signed nonce")
    if not re.search(r"^Status: Granted\.$", reply_text, re.MULTILINE):
        raise ValueError("RFC3161 token must have granted status")
    policy_re = r"^Policy OID: " + re.escape(expected_policy_oid) + r"$"
    if not re.search(policy_re, reply_text, re.MULTILINE):
        raise ValueError("RFC3161 token policy is not predeclared policy")

    bar_closed_ns = (source_origin_hour_utc + 3600) * SECOND_NS
    row_info: list[dict[str, object]] = []
    for h in HORIZONS_HOURS:
        target_hour = source_origin_hour_utc + (h + 1) * 3600
        target_close = source_origin_hour_utc + (h + 2) * 3600
        lead_ns = target_close * SECOND_NS - stamp_ns
        eligible = stamp_ns >= bar_closed_ns and lead_ns >= h * HOUR_NS
        row_info.append(
            {
                "horizon_hours": h,
                "training_target_row_shift": h + 1,
                "target_hour_utc": target_hour,
                "target_close_utc": target_close,
                "signed_elapsed_lead_ns": lead_ns,
                "signed_minimum_elapsed_eligible": eligible,
            }
        )
    eligible_all = all(bool(row["signed_minimum_elapsed_eligible"]) for row in row_info)
    return {
        "status": (
            "CONFIGURED_TSA_SIGNED_PREDEADLINE_BUNDLE_UNVERIFIED_CUSTODY"
            if eligible_all
            else "CONFIGURED_TSA_SIGNED_BUT_OUTSIDE_PREDECLARED_WINDOW"
        ),
        "forecast_bundle_sha256": expected_bundle_sha256,
        "tsa_trust_root_sha256": expected_root_pem_sha256,
        "tsa_signing_cert_sha256": expected_signer_cert_sha256,
        "tsa_signer_cert_validity_checked_at_signed_time": True,
        "tsa_signer_independently_preapproved_by_this_function": False,
        "tsa_policy_oid": expected_policy_oid,
        "tsa_signed_utc_time_ns": stamp_ns,
        "rfc3161_signature_nonce_imprint_and_configured_chain_verified": True,
        "forecast_bytes_bound_to_real_committed_git_blob_by_this_function": False,
        "trust_root_independently_preapproved_by_this_function": False,
        "tsa_certificate_revocation_independently_checked": False,
        "public_forecast_availability_independently_proven": False,
        "all_full_elapsed_horizons_eligible_against_signed_time": eligible_all,
        "horizons": row_info,
        "scientific_authorization": "NO_RUN",
    }
