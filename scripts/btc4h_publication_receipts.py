"""First-party remote-publication upper-bound receipts for BTC 4h research.

Git's remote-ref ACK plus a local post-fetch wall clock is an operational
upper bound, NOT independent authoritative GitHub server time. The checks
fail closed when receipt collection happens after a target became known.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.btc4h_shadow_audit import _parse_utc, _validate_forecast
from scripts.btc4h_shadow_forward import VERSION, _append, _read_jsonl, iso, utc


def _line_hash(row: dict[str, Any]) -> str:
    encoded = json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _commit_sha(value: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 40
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise ValueError("expected 40-character Git commit SHA1")
    return value


def make_issue_receipt(
    forecast: dict[str, Any],
    *,
    remote_commit_sha: str,
    fetched_remote_sha: str,
    confirmed_at_utc: datetime,
    run_id: str,
) -> dict[str, Any]:
    """Validate an already pushed forecast before permitting it to be scored.

    The Git remote-ref comparison itself must be done by the caller, and the
    GitHub-runner clock remains untrusted by an independent custodian.
    """
    utc(confirmed_at_utc)
    commit = _commit_sha(remote_commit_sha)
    if _commit_sha(fetched_remote_sha) != commit:
        raise ValueError("remote confirmed ref does not match pushed issue commit")
    if not isinstance(run_id, str) or not run_id or len(run_id) > 80:
        raise ValueError("missing/invalid workflow run ID")
    _validate_forecast(forecast, confirmed_at_utc)
    target_end = _parse_utc(forecast["target_5m_close_utc"])
    issue_time = _parse_utc(forecast["issued_at_utc"])
    if not issue_time <= confirmed_at_utc < target_end:
        raise ValueError("remote publication not confirmed before target closed")
    return {
        "version": VERSION,
        "origin_utc": forecast["origin_utc"],
        "issued_at_utc": forecast["issued_at_utc"],
        "target_5m_close_utc": forecast["target_5m_close_utc"],
        "first_party_remote_confirmed_at_utc": iso(confirmed_at_utc),
        "remote_issue_commit_sha": commit,
        "forecast_canonical_line_sha256": _line_hash(forecast),
        "workflow_run_id": run_id,
        "remote_ref_was_fetched_and_compared": True,
        "independent_time_witness": False,
    }


def validate_receipts(
    forecasts: list[dict[str, Any]],
    receipts: list[dict[str, Any]],
    *,
    as_of_utc: datetime,
) -> dict[str, Any]:
    """Require exactly one matching timely first-party receipt per issue.

    This is an internal equality check, NOT cryptographic proof that the
    remote Git commit existed at the claimed wall-clock time.
    """
    utc(as_of_utc)
    expected: dict[str, dict[str, Any]] = {}
    for row in forecasts:
        _validate_forecast(row, as_of_utc)
        key = row["origin_utc"]
        if key in expected:
            raise ValueError("duplicate forecast origin")
        expected[key] = row
    seen: set[str] = set()
    for receipt in receipts:
        if receipt.get("version") != VERSION:
            raise ValueError("unrecognized issue publication receipt")
        key = receipt["origin_utc"]
        if key not in expected:
            raise ValueError("orphan publication receipt")
        if key in seen:
            raise ValueError("duplicate publication receipt")
        seen.add(key)
        row = expected[key]
        stamp = _parse_utc(receipt["first_party_remote_confirmed_at_utc"])
        if stamp > as_of_utc:
            raise ValueError("future-dated remote receipt")
        if receipt["issued_at_utc"] != row["issued_at_utc"]:
            raise ValueError("receipt issue clock mismatch")
        if receipt["target_5m_close_utc"] != row["target_5m_close_utc"]:
            raise ValueError("receipt target close mismatch")
        if receipt["forecast_canonical_line_sha256"] != _line_hash(row):
            raise ValueError("receipt forecast hash mismatch")
        if receipt.get("remote_ref_was_fetched_and_compared") is not True:
            raise ValueError("no remote-ref confirmation asserted")
        if receipt.get("independent_time_witness") is not False:
            raise ValueError("unjustified independent witness claim")
        _commit_sha(receipt["remote_issue_commit_sha"])
        if not isinstance(receipt.get("workflow_run_id"), str) or not receipt["workflow_run_id"]:
            raise ValueError("missing issue workflow run")
        if stamp < _parse_utc(row["issued_at_utc"]) or stamp >= _parse_utc(
            row["target_5m_close_utc"]
        ):
            raise ValueError("publication confirmation not in pre-target window")
    missing = set(expected) - seen
    if missing:
        raise ValueError(f"{len(missing)} forecast(s) missing timely remote receipts")
    return {
        "issued_forecasts": len(expected),
        "confirmed_remote_receipts": len(seen),
        "unconfirmed_issued_forecasts": 0,
        "independently_witnessed": False,
    }


def write_latest_receipt(
    ledger: Path,
    receipt_ledger: Path,
    *,
    remote_commit_sha: str,
    confirmed_at_utc: datetime,
    run_id: str,
) -> dict[str, Any]:
    """Append a receipt only for a new forecast (never manufacture a backfill)."""
    forecasts = _read_jsonl(ledger)
    if not forecasts:
        raise ValueError("no issue in forecast ledger to confirm")
    current = forecasts[-1]
    existing = _read_jsonl(receipt_ledger)
    if any(row["origin_utc"] == current["origin_utc"] for row in existing):
        raise ValueError("a publication receipt already exists for this origin")
    receipt = make_issue_receipt(
        current,
        remote_commit_sha=remote_commit_sha,
        fetched_remote_sha=remote_commit_sha,
        confirmed_at_utc=confirmed_at_utc,
        run_id=run_id,
    )
    _append(receipt_ledger, receipt)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issues", type=Path, required=True)
    parser.add_argument("--receipts", type=Path, required=True)
    parser.add_argument("--remote-sha", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    confirmed_at = datetime.now(UTC)
    receipt = write_latest_receipt(
        args.issues,
        args.receipts,
        remote_commit_sha=args.remote_sha,
        confirmed_at_utc=confirmed_at,
        run_id=args.run_id,
    )
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
