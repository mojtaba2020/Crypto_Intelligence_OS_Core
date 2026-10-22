"""Offline, opt-in receipt for prospective BTC source-response observations.

This records when *our process* received bytes, NOT when the exchange first
published them. No provider calls, price parsing, backdating, model fitting,
locked-OOS access, or external attestation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path

MAX_RESPONSE_BYTES = 1_000_000
SOURCES = frozenset(
    {
        "bitstamp:BTCUSD:1h",
        "bitstamp:BTCUSD:1d",
        "bitfinex:BTCUSD:1h",
        "bitfinex:BTCUSD:1d",
    }
)
FIELDS = frozenset(
    {
        "schema_version",
        "status",
        "source",
        "bar_open_utc",
        "bar_seconds",
        "system_observed_at_utc",
        "raw_response_sha256",
        "raw_response_bytes",
        "source_first_publication_authenticated",
        "external_immutable_seal_verified",
        "stage6_run_authorized",
        "receipt_sha256",
    }
)
STATUS = "LOCAL_OBSERVATION_ONLY_UNATTESTED"


def _serialized(value: Mapping[str, object]) -> bytes:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return (payload + "\n").encode("utf-8")


def _validate_metadata(source: object, opening: object, seconds: object) -> None:
    if type(source) is not str or source not in SOURCES:
        raise ValueError("Unapproved source identity")
    if type(seconds) is not int or seconds not in (3_600, 86_400):
        raise ValueError("Source bar seconds must be 3600 or 86400")
    if type(opening) is not int or opening <= 0 or opening % seconds:
        raise ValueError("Bar opening must be a canonical positive UTC epoch second")
    suffix = "1h" if seconds == 3_600 else "1d"
    if not source.endswith(":" + suffix):
        raise ValueError("Source cadence/identity mismatch")


def _observed_at(value: object) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("A timezone-aware UTC local observation is required")
    if value.utcoffset() != timedelta(0):
        raise ValueError("Observation clock must use UTC")
    return value.astimezone(UTC)


def make_local_receipt(
    raw_response: bytes,
    *,
    source: str,
    bar_open_utc: int,
    bar_seconds: int,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    """Digest already-received response bytes at a local post-receipt clock tick."""
    _validate_metadata(source, bar_open_utc, bar_seconds)
    if type(raw_response) is not bytes or not 0 < len(raw_response) <= MAX_RESPONSE_BYTES:
        raise ValueError("Raw response must be nonempty bounded bytes")
    # Mark only *after* the bytes are already available; never substitute candle-close
    # for actual system observation time. The clock itself is not trusted attestation.
    observed = _observed_at((clock or (lambda: datetime.now(UTC)))())
    if observed.timestamp() < bar_open_utc + bar_seconds:
        raise ValueError("Bar cannot be observed as finalized before its nominal close")
    receipt: dict[str, object] = {
        "schema_version": 1,
        "status": STATUS,
        "source": source,
        "bar_open_utc": bar_open_utc,
        "bar_seconds": bar_seconds,
        "system_observed_at_utc": observed.isoformat(timespec="microseconds").replace(
            "+00:00", "Z"
        ),
        "raw_response_sha256": hashlib.sha256(raw_response).hexdigest(),
        "raw_response_bytes": len(raw_response),
        "source_first_publication_authenticated": False,
        "external_immutable_seal_verified": False,
        "stage6_run_authorized": False,
    }
    receipt["receipt_sha256"] = hashlib.sha256(_serialized(receipt)).hexdigest()
    return receipt


def validate_local_receipt(receipt: Mapping[str, object]) -> None:
    """Detect accidental mutation; a self-hash is NOT third-party source proof."""
    if not isinstance(receipt, Mapping) or set(receipt) != FIELDS:
        raise ValueError("Unexpected receipt schema")
    _validate_metadata(receipt["source"], receipt["bar_open_utc"], receipt["bar_seconds"])
    if type(receipt["schema_version"]) is not int or receipt["schema_version"] != 1:
        raise ValueError("Unsupported receipt version")
    if type(receipt["status"]) is not str or receipt["status"] != STATUS:
        raise ValueError("Unsupported receipt status")
    for key in (
        "source_first_publication_authenticated",
        "external_immutable_seal_verified",
        "stage6_run_authorized",
    ):
        if receipt[key] is not False:
            raise ValueError("Receipt cannot assert third-party approval")
    stamp = receipt["system_observed_at_utc"]
    if not isinstance(stamp, str) or not stamp.endswith("Z"):
        raise ValueError("Observation timestamp must be canonical UTC")
    try:
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid observation timestamp") from exc
    observed = _observed_at(parsed)
    if stamp != observed.isoformat(timespec="microseconds").replace("+00:00", "Z"):
        raise ValueError("Noncanonical UTC timestamp")
    if observed.timestamp() < receipt["bar_open_utc"] + receipt["bar_seconds"]:
        raise ValueError("Receipt precedes nominal bar close")
    raw_digest = receipt["raw_response_sha256"]
    receipt_digest = receipt["receipt_sha256"]
    if (
        type(receipt["raw_response_bytes"]) is not int
        or not 0 < receipt["raw_response_bytes"] <= MAX_RESPONSE_BYTES
        or not isinstance(raw_digest, str)
        or len(raw_digest) != 64
        or any(ch not in "0123456789abcdef" for ch in raw_digest)
        or not isinstance(receipt_digest, str)
    ):
        raise ValueError("Invalid raw-response identity")
    digest = hashlib.sha256(
        _serialized({key: value for key, value in receipt.items() if key != "receipt_sha256"})
    ).hexdigest()
    if digest != receipt_digest:
        raise ValueError("Receipt self-checksum mismatch")


def save_private_receipt(receipt: Mapping[str, object], private_root: Path) -> Path:
    """Disabled: private-root path checks cannot attest an immutable OS namespace.

    Even a pinned directory fd can be MOVED into a public Git checkout after a
    path check by another actor with parent rename privilege. There is no
    general safe in-process pathname recheck against this race. A separate
    restricted operator with independently verified OS isolation, fixed mount
    and custody policy must own persistence before a new implementation is
    approved. No filesystem operations are performed here.
    """
    raise PermissionError(
        "Stage-6 receipt persistence disabled pending independent OS isolation approval"
    )
