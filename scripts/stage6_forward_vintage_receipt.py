"""Offline, opt-in receipt for prospective BTC source-response observations.

This records when *our process* received bytes, NOT when the exchange first
published them. No provider calls, price parsing, backdating, model fitting,
locked-OOS access, or external attestation.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
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
    """Single create-only file, outside the Git repo; never store response bytes.

    Does not prove append-only *external* custody. Operators must separately seal
    receipts and provide independent source-clock and filesystem attestations.
    """
    validate_local_receipt(receipt)
    if not private_root.is_absolute():
        raise ValueError("Receipt root must be absolute")
    if any(p.is_symlink() for p in (private_root, *private_root.parents)):
        raise ValueError("Receipt root must not have symlinked ancestors")
    resolved = private_root.resolve(strict=True)
    repo_root = Path(__file__).resolve().parents[1]
    if resolved.is_relative_to(repo_root):
        raise ValueError("Never store observation receipts in public GitHub repository")
    if not private_root.is_dir() or private_root.stat().st_mode & 0o077:
        raise ValueError("Receipt root must be an existing private directory (0700)")
    observed = datetime.fromisoformat(str(receipt["system_observed_at_utc"]).replace("Z", "+00:00"))
    # Exact integer epoch microseconds: never round receipt IDs through float time.
    elapsed = observed - datetime(1970, 1, 1, tzinfo=UTC)
    stamp_us = ((elapsed.days * 86_400 + elapsed.seconds) * 1_000_000) + elapsed.microseconds
    filename = f"stage6-{stamp_us}-{receipt['receipt_sha256'][:20]}.json"
    root_fd = os.open(private_root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | os.O_NOFOLLOW)
    try:
        if not stat.S_ISDIR(os.fstat(root_fd).st_mode):
            raise ValueError("Receipt root changed during open")
        descriptor = os.open(
            filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=root_fd
        )
        with os.fdopen(descriptor, "wb") as output:
            output.write(_serialized(receipt))
            output.flush()
            os.fsync(output.fileno())
        os.fsync(root_fd)
    finally:
        os.close(root_fd)
    return resolved / filename
