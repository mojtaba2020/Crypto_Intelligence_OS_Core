"""Synthetic-only tests for the opt-in Stage-6 forward vintage receipts."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from scripts.stage6_forward_vintage_receipt import (
    make_local_receipt,
    save_private_receipt,
    validate_local_receipt,
)

DAY = 86_400
OPEN = int(datetime(2026, 10, 12, tzinfo=UTC).timestamp())
NOW = datetime(2026, 10, 13, 7, 45, tzinfo=UTC)
RAW = b'{"synthetic_response":true,"bar":"not_real"}'


def _make(**kwargs: object) -> dict[str, object]:
    args: dict[str, object] = {
        "source": "bitstamp:BTCUSD:1d",
        "bar_open_utc": OPEN,
        "bar_seconds": DAY,
        "clock": lambda: NOW,
    }
    args.update(kwargs)
    return make_local_receipt(RAW, **args)


def test_receipt_has_only_local_observation_no_unauthorized_claims() -> None:
    packet = _make()
    validate_local_receipt(packet)
    assert packet["system_observed_at_utc"] == "2026-10-13T07:45:00.000000Z"
    assert packet["source_first_publication_authenticated"] is False
    assert packet["external_immutable_seal_verified"] is False
    assert packet["stage6_run_authorized"] is False
    assert "synthetic_response" not in json.dumps(packet)
    assert packet["raw_response_bytes"] == len(RAW)


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("source", "unknown"),
        ("source", []),
        ("source", {"unexpected": "object"}),
        ("source", "bitfinex:BTCUSD:1w"),
        ("bar_open_utc", True),
        ("bar_open_utc", OPEN + 1),
        ("bar_seconds", 60),
        ("bar_seconds", 3_600),
    ],
)
def test_invalid_identity_or_source_cadence_rejected(field: str, invalid: object) -> None:
    with pytest.raises(ValueError):
        _make(**{field: invalid})


@pytest.mark.parametrize("raw", [b"", b"x" * 1_000_001, "not-bytes"])
def test_raw_response_is_bounded(raw: object) -> None:
    with pytest.raises(ValueError, match="bounded bytes"):
        make_local_receipt(
            raw,
            source="bitstamp:BTCUSD:1d",
            bar_open_utc=OPEN,
            bar_seconds=DAY,
            clock=lambda: NOW,
        )


def test_observation_not_backdated_to_market_bar_close() -> None:
    too_early = datetime(2026, 10, 12, 12, tzinfo=UTC)
    with pytest.raises(ValueError, match="nominal close"):
        _make(clock=lambda: too_early)


@pytest.mark.parametrize(
    "clock",
    [
        lambda: datetime(2026, 10, 13),
        lambda: NOW.astimezone(timezone(timedelta(hours=-5))),
        lambda: "2026-10-13",
    ],
)
def test_local_clock_requires_actual_utc_aware_datetime(clock: object) -> None:
    with pytest.raises(ValueError, match=r"UTC|timezone"):
        _make(clock=clock)


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("source_first_publication_authenticated", True),
        ("external_immutable_seal_verified", True),
        ("stage6_run_authorized", True),
        ("raw_response_sha256", "0" * 64),
        ("system_observed_at_utc", "2026-10-12T00:00:00.000000Z"),
        ("raw_response_bytes", 99),
    ],
)
def test_self_hash_does_not_allow_tampering(field: str, invalid: object) -> None:
    packet = _make()
    packet[field] = invalid
    with pytest.raises(ValueError):
        validate_local_receipt(packet)


def test_boolean_version_cannot_masquerade_as_schema_one_with_rehashed_receipt() -> None:
    from scripts.stage6_forward_vintage_receipt import _serialized

    packet = _make()
    packet["schema_version"] = True  # True == 1 under Python equality: reject by type.
    unsigned = {k: v for k, v in packet.items() if k != "receipt_sha256"}
    packet["receipt_sha256"] = hashlib.sha256(_serialized(unsigned)).hexdigest()
    with pytest.raises(ValueError, match="version"):
        validate_local_receipt(packet)


def test_validator_rejects_unhashable_source_instead_of_crashing() -> None:
    packet = _make()
    packet["source"] = []
    with pytest.raises(ValueError, match="source identity"):
        validate_local_receipt(packet)


def test_extra_price_or_target_fields_rejected() -> None:
    packet = _make()
    packet["actual_future_price"] = 120_000
    with pytest.raises(ValueError, match="schema"):
        validate_local_receipt(packet)


@pytest.mark.parametrize("root_kind", ["private", "relative", "public", "symlink"])
def test_disk_receipt_persistence_is_disabled_no_matter_the_path(
    tmp_path: Path, root_kind: str
) -> None:
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    if root_kind == "private":
        root = private
    elif root_kind == "relative":
        root = Path("relative-not-to-be-created")
    elif root_kind == "public":
        root = tmp_path / "public"
        root.mkdir(mode=0o755)
    else:
        root = tmp_path / "alias"
        root.symlink_to(private, target_is_directory=True)

    with pytest.raises(PermissionError, match="disabled pending independent OS isolation"):
        save_private_receipt(_make(), root)

    assert list(private.iterdir()) == []
    assert not list(tmp_path.glob("**/stage6-*.json"))


def test_same_raw_bytes_at_two_clock_ticks_still_produce_distinct_local_claims() -> None:
    earlier = _make(clock=lambda: NOW)
    later = _make(clock=lambda: NOW + timedelta(seconds=1))
    assert earlier["raw_response_sha256"] == later["raw_response_sha256"]
    assert earlier["receipt_sha256"] != later["receipt_sha256"]
    assert earlier["external_immutable_seal_verified"] is False
    assert later["stage6_run_authorized"] is False
