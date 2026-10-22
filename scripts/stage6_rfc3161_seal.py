"""Offline RFC3161 evidence verifier for a future-only, versioned Stage-6 lane.

No network, no certificate/secret generation, no market data processing and no
scientific promotion. The TSA trust root MUST be approved and pinned outside
this module before meaningful independent attestation is claimed.
"""

from __future__ import annotations

import calendar
import hashlib
import hmac
import json
import math
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
_ACCURACY_ENTRY = re.compile(r"(?P<hex>0x[0-9A-Fa-f]+) (?P<unit>seconds|millis|micros)")
BUNDLE_TIMESTAMP_RE = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?(?:Z|\+00:00)$")
SIGNED_FORECAST_VERSION = "stage6-hourly-full-elapsed-v1-research-only"
SIGNED_ROW_FIELDS = frozenset(
    {
        "version",
        "issued_at_utc",
        "origin_hour_utc",
        "target_hour_utc",
        "target_close_utc",
        "horizon_hours",
        "origin_close_usd",
        "forecast_usd",
        "persistence_usd",
        "observed_volatility_hourly",
        "training_hours",
        "resolved_training_examples",
        "holdout_selected_blend",
        "source",
        "research_only",
    }
)
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


def _unique_json_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate key in signed forecast record")
        result[key] = value
    return result


def _invalid_json_constant(value: str) -> None:
    raise ValueError("Non-finite signed JSON value not permitted")


def _strict_utc_ns(value: object, field: str) -> int:
    if not isinstance(value, str) or not BUNDLE_TIMESTAMP_RE.fullmatch(value):
        raise ValueError(f"Signed {field} must be UTC with explicit Z or +00:00")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Invalid signed {field}") from exc
    if stamp.utcoffset() is None or stamp.utcoffset().total_seconds() != 0:
        raise ValueError(f"Signed {field} must use UTC")
    return calendar.timegm(stamp.timetuple()) * SECOND_NS + stamp.microsecond * 1000



def _signed_accuracy_ns(text: str) -> int:
    """Parse RFC3161 token accuracy; never assume a zero absent-policy error."""
    matches = re.findall(r"^Accuracy: (.+)$", text, flags=re.MULTILINE)
    if len(matches) != 1:
        raise ValueError("Signed timestamp accuracy is missing or ambiguous")
    components = matches[0].split(", ")
    if not 1 <= len(components) <= 3:
        raise ValueError("Signed timestamp accuracy syntax invalid")
    scales = {"seconds": SECOND_NS, "millis": 1_000_000, "micros": 1_000}
    observed: set[str] = set()
    total = 0
    for component in components:
        parsed = _ACCURACY_ENTRY.fullmatch(component)
        if parsed is None:
            raise ValueError("Signed timestamp accuracy syntax invalid")
        unit = parsed.group("unit")
        value = int(parsed.group("hex"), 16)
        if unit in observed or (unit in {"millis", "micros"} and not 1 <= value <= 999):
            raise ValueError("Signed timestamp accuracy unit invalid")
        if unit == "seconds" and value > 86_400:
            raise ValueError("Signed timestamp accuracy exceeds allowed bound")
        observed.add(unit)
        total += value * scales[unit]
    return total


def _is_minimum_elapsed_eligible(
    *,
    source_close_ns: int,
    target_close_ns: int,
    horizon_hours: int,
    signed_time_lower_ns: int,
    signed_time_upper_ns: int,
) -> bool:
    """Only a timestamp wholly after source close AND before horizon deadline qualifies."""
    return (
        signed_time_lower_ns > source_close_ns
        and target_close_ns - signed_time_upper_ns >= horizon_hours * HOUR_NS
    )


def _validate_signed_forecast_numeric_fields(row: dict[str, object]) -> None:
    """Reject boolean, null, NaN, overflow-to-infinity, or mis-typed signed fields."""
    for key in ("origin_close_usd", "forecast_usd", "persistence_usd"):
        value = row[key]
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError("Signed forecast prices must be finite positive numbers")
    volatility = row["observed_volatility_hourly"]
    if type(volatility) not in (int, float) or not math.isfinite(volatility) or volatility < 0:
        raise ValueError("Signed observed volatility must be finite and nonnegative")
    weight = row["holdout_selected_blend"]
    if type(weight) not in (int, float) or not math.isfinite(weight) or not 0 <= weight <= 1:
        raise ValueError("Signed blend weight must be finite and within [0,1]")
    for key in ("training_hours", "resolved_training_examples"):
        value = row[key]
        if type(value) is not int or value <= 0:
            raise ValueError("Signed training counts must be positive integers")

def _check_four_signed_forecasts(bundle: bytes, source_origin: int, gen_ns: int) -> None:
    """Derive the origin and H+1 targets from signed bytes, never caller metadata."""
    if b"\r" in bundle or not bundle.endswith(b"\n"):
        raise ValueError("Signed forecast bundle must be canonical newline-complete JSONL")
    lines = bundle.splitlines(keepends=True)
    if len(lines) != len(HORIZONS_HOURS) or any(not line.endswith(b"\n") for line in lines):
        raise ValueError("Exactly four signed forecast JSONL rows required")
    expected_origin_ns = source_origin * SECOND_NS
    issues: set[int] = set()
    for line, horizon in zip(lines, HORIZONS_HOURS, strict=True):
        try:
            row = json.loads(
                line.decode("utf-8"),
                object_pairs_hook=_unique_json_pairs,
                parse_constant=_invalid_json_constant,
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Malformed signed forecast JSONL") from exc
        if (
            type(row) is not dict
            or set(row) != SIGNED_ROW_FIELDS
            or row.get("version") != SIGNED_FORECAST_VERSION
            or row.get("research_only") is not True
            or row.get("source") != "coinbase:exchange:BTC-USD:1h:close"
            or type(row.get("horizon_hours")) is not int
            or row["horizon_hours"] != horizon
        ):
            raise ValueError("Signed forecast version, horizon or schema mismatch")
        _validate_signed_forecast_numeric_fields(row)
        origin_ns = _strict_utc_ns(row["origin_hour_utc"], "origin")
        issue_ns = _strict_utc_ns(row["issued_at_utc"], "issuance")
        target_hour_ns = _strict_utc_ns(row["target_hour_utc"], "target hour")
        target_close_ns = _strict_utc_ns(row["target_close_utc"], "target close")
        if origin_ns != expected_origin_ns:
            raise ValueError("Signed forecast origin differs from declared source origin")
        if target_hour_ns != (source_origin + (horizon + 1) * 3600) * SECOND_NS:
            raise ValueError("Signed forecast target hour does not match H+1 label shift")
        if target_close_ns != (source_origin + (horizon + 2) * 3600) * SECOND_NS:
            raise ValueError("Signed forecast target close does not match H+1 label shift")
        if not (origin_ns + HOUR_NS < issue_ns <= gen_ns):
            raise ValueError("Signed forecast issuance outside source-close-to-token window")
        issues.add(issue_ns)
    if len(issues) != 1:
        raise ValueError("Signed forecast bundle contains mixed issuance timestamps")


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
    if type(expected_signer_cert_sha256) is not str or not SHA256_HEX.fullmatch(
        expected_signer_cert_sha256
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
            openssl_path,
            "ts",
            "-reply",
            "-in",
            str(temp / "response"),
            "-token_out",
            "-out",
            str(temp / "token.der"),
        )
        _openssl(
            openssl_path,
            "cms",
            "-verify",
            "-inform",
            "DER",
            "-in",
            str(temp / "token.der"),
            "-noverify",
            "-binary",
            "-signer",
            str(temp / "actual_signer.pem"),
            "-out",
            str(temp / "verified_tstinfo.der"),
        )
        signer_bytes = (temp / "actual_signer.pem").read_bytes()
        if signer_bytes.count(b"-----BEGIN CERTIFICATE-----") != 1:
            raise ValueError("RFC3161 token must contain exactly one CMS signer")
        fingerprint_line = _openssl(
            openssl_path,
            "x509",
            "-in",
            str(temp / "actual_signer.pem"),
            "-noout",
            "-fingerprint",
            "-sha256",
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
                openssl_path,
                "ts",
                "-verify",
                *timed_args,
                "-queryfile",
                str(temp / "query"),
            )
            _openssl(
                openssl_path,
                "ts",
                "-verify",
                *timed_args,
                "-data",
                str(temp / "payload"),
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

    # A signed token must authenticate its OWN four-row origin/target calendar.
    # Caller-provided source_origin cannot promote an older, valid signature.
    _check_four_signed_forecasts(bundle, source_origin_hour_utc, stamp_ns)
    accuracy_ns = _signed_accuracy_ns(reply_text)
    signed_time_lower_ns = stamp_ns - accuracy_ns
    signed_time_upper_ns = stamp_ns + accuracy_ns
    bar_closed_ns = (source_origin_hour_utc + 3600) * SECOND_NS
    row_info: list[dict[str, object]] = []
    for h in HORIZONS_HOURS:
        target_hour = source_origin_hour_utc + (h + 1) * 3600
        target_close = source_origin_hour_utc + (h + 2) * 3600
        target_close_ns = target_close * SECOND_NS
        lead_ns = target_close_ns - signed_time_upper_ns
        eligible = _is_minimum_elapsed_eligible(
            source_close_ns=bar_closed_ns,
            target_close_ns=target_close_ns,
            horizon_hours=h,
            signed_time_lower_ns=signed_time_lower_ns,
            signed_time_upper_ns=signed_time_upper_ns,
        )
        row_info.append(
            {
                "horizon_hours": h,
                "training_target_row_shift": h + 1,
                "target_hour_utc": target_hour,
                "target_close_utc": target_close,
                "conservative_signed_elapsed_lead_ns": lead_ns,
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
        "tsa_signed_accuracy_ns": accuracy_ns,
        "tsa_signed_utc_time_lower_ns": signed_time_lower_ns,
        "tsa_signed_utc_time_upper_ns": signed_time_upper_ns,
        "accuracy_source": "token_embedded_accuracy",
        "rfc3161_signature_nonce_imprint_and_configured_chain_verified": True,
        "signed_four_forecast_origin_and_target_calendar_verified": True,
        "forecast_bytes_bound_to_real_committed_git_blob_by_this_function": False,
        "trust_root_independently_preapproved_by_this_function": False,
        "tsa_certificate_revocation_independently_checked": False,
        "public_forecast_availability_independently_proven": False,
        "all_full_elapsed_horizons_eligible_against_signed_time": eligible_all,
        "horizons": row_info,
        "scientific_authorization": "NO_RUN",
    }
