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


def test_adjacent_microsecond_receipts_have_distinct_exact_filenames(tmp_path: Path) -> None:
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    first = save_private_receipt(_make(clock=lambda: NOW.replace(microsecond=2)), root)
    second = save_private_receipt(_make(clock=lambda: NOW.replace(microsecond=3)), root)
    expected_us = int(NOW.timestamp()) * 1_000_000
    assert first != second
    assert first.name.startswith(f"stage6-{expected_us + 2}-")
    assert second.name.startswith(f"stage6-{expected_us + 3}-")


def test_extra_price_or_target_fields_rejected() -> None:
    packet = _make()
    packet["actual_future_price"] = 120_000
    with pytest.raises(ValueError, match="schema"):
        validate_local_receipt(packet)


def test_private_create_only_storage_cannot_overwrite_and_never_saves_raw(tmp_path: Path) -> None:
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    receipt = _make()
    destination = save_private_receipt(receipt, root)
    assert destination.is_file()
    assert destination.stat().st_mode & 0o077 == 0
    persisted = destination.read_text()
    assert persisted.startswith("{")
    assert RAW not in destination.read_bytes()
    assert json.loads(persisted) == receipt
    with pytest.raises(FileExistsError):
        save_private_receipt(receipt, root)
    assert json.loads(destination.read_text()) == receipt


def test_unsecured_directory_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "world-readable"
    root.mkdir()
    root.chmod(0o755)
    with pytest.raises(ValueError, match="private directory"):
        save_private_receipt(_make(), root)
    assert not list(root.glob("*.json"))


def test_symlinked_receipt_root_rejected(tmp_path: Path) -> None:
    root = tmp_path / "real"
    root.mkdir(mode=0o700)
    alias = tmp_path / "alias"
    alias.symlink_to(root, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        save_private_receipt(_make(), alias)
    assert not list(root.iterdir())


def test_refuses_relative_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="absolute"):
        save_private_receipt(_make(), Path("private"))


def test_unchanged_source_bytes_at_new_observation_time_are_distinct(tmp_path: Path) -> None:
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    earlier = _make(clock=lambda: NOW)
    later = _make(clock=lambda: NOW + timedelta(seconds=1))
    first = save_private_receipt(earlier, root)
    second = save_private_receipt(later, root)
    assert first != second
    assert earlier["raw_response_sha256"] == later["raw_response_sha256"]
    assert earlier["receipt_sha256"] != later["receipt_sha256"]


def test_permission_change_during_root_open_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    real_open = os.open

    def chmod_before_open(path: object, flags: int, *args: object, **kwargs: object) -> int:
        if path == root:
            root.chmod(0o755)
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", chmod_before_open)
    with pytest.raises(ValueError, match="insecure during open"):
        save_private_receipt(_make(), root)
    assert not list(root.iterdir())


def test_directory_replacement_during_root_open_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    root = tmp_path / "private"
    moved = tmp_path / "moved"
    root.mkdir(mode=0o700)
    real_open = os.open

    def swap_before_open(path: object, flags: int, *args: object, **kwargs: object) -> int:
        if path == root:
            root.rename(moved)
            root.mkdir(mode=0o700)
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", swap_before_open)
    with pytest.raises(ValueError, match="changed or became insecure"):
        save_private_receipt(_make(), root)
    assert not list(root.iterdir())
    assert not list(moved.iterdir())


def test_ancestor_symlink_swap_cannot_redirect_receipt_into_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scripts.stage6_forward_vintage_receipt as receipt_module

    checkout = tmp_path / "fake-public-checkout"
    (checkout / "scripts").mkdir(parents=True)
    public_dest = checkout / "private"
    public_dest.mkdir(mode=0o700)
    carrier = tmp_path / "carrier"
    carrier.mkdir(mode=0o700)
    root = carrier / "private"
    root.mkdir(mode=0o700)
    moved = tmp_path / "moved-carrier"

    # Recreate the real failure: resolve() was safe, then an ancestor becomes
    # a symlink into the public checkout immediately before root.stat().
    monkeypatch.setattr(
        receipt_module, "__file__", str(checkout / "scripts" / "stage6_forward_vintage_receipt.py")
    )
    real_stat = Path.stat
    swapped = False

    def replace_ancestor_during_stat(
        path: Path, *args: object, **kwargs: object
    ) -> object:
        nonlocal swapped
        if path == root and not swapped:
            swapped = True
            carrier.rename(moved)
            carrier.symlink_to(checkout, target_is_directory=True)
        return real_stat(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "stat", replace_ancestor_during_stat)
        with pytest.raises(ValueError, match="changed or became public"):
            save_private_receipt(_make(), root)
    assert swapped
    assert not list(public_dest.iterdir())


def test_short_write_failure_removes_placeholder_and_allows_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import errno
    import os

    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    payload = _make()
    real_fdopen = os.fdopen

    class ShortWrite:
        def __init__(self, fd: int, mode: str) -> None:
            self.handle = real_fdopen(fd, mode)

        def __enter__(self) -> ShortWrite:
            return self

        def __exit__(self, *args: object) -> object:
            return self.handle.__exit__(*args)

        def write(self, data: bytes) -> None:
            self.handle.write(data[:10])
            raise OSError(errno.ENOSPC, "synthetic disk full")

    with monkeypatch.context() as patch:
        patch.setattr(os, "fdopen", lambda fd, mode: ShortWrite(fd, mode))
        with pytest.raises(OSError, match="synthetic disk full"):
            save_private_receipt(payload, root)
    assert list(root.iterdir()) == []

    destination = save_private_receipt(payload, root)
    assert json.loads(destination.read_text()) == payload
