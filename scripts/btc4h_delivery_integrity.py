"""First-party Git publication checks; these are not independent time attestation."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from typing import Any


def at(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("receipt timestamp must be an ISO8601 UTC string")
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None or stamp.utcoffset() != UTC.utcoffset(stamp):
        raise ValueError("receipt timestamps must be aware UTC")
    return stamp


def canonical_line(row: dict[str, Any]) -> bytes:
    return (json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode()


def canonical_digest(row: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_line(row)).hexdigest()


def validate_receipt(forecast: dict[str, Any], receipt: dict[str, Any]) -> None:
    for key in ("version", "origin_utc", "issued_at_utc", "target_5m_close_utc"):
        if receipt.get(key) != forecast[key]:
            raise ValueError(f"receipt mismatch: {key}")
    if receipt.get("forecast_canonical_line_sha256") != canonical_digest(forecast):
        raise ValueError("receipt canonical SHA256 mismatch")
    commit_sha = receipt.get("remote_issue_commit_sha")
    if not isinstance(commit_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
        raise ValueError("invalid remote commit SHA")
    if receipt.get("remote_ref_was_fetched_and_compared") is not True:
        raise ValueError("remote Git was not verified")
    if receipt.get("independent_time_witness") is not False:
        raise ValueError("first-party receipt must not claim independent attestation")
    if (
        not at(forecast["issued_at_utc"])
        <= at(receipt["first_party_remote_confirmed_at_utc"])
        < at(forecast["target_5m_bar_open_utc"])
    ):
        raise ValueError("receipt not confirmed before target candle opened")
    if forecast["version"] == "btc4h-continuous-v2-ridge100":
        confirmed = at(receipt["first_party_remote_confirmed_at_utc"])
        close = at(forecast["target_5m_close_utc"])
        if close - confirmed < timedelta(hours=4):
            raise ValueError("remote publication leaves less than four hours to target")


def verify_stored_receipt(
    forecast: dict[str, Any], receipt: dict[str, Any], ledger_path: str
) -> None:
    validate_receipt(forecast, receipt)
    # The commit identifier is validated above; pass arguments without a shell.
    content = subprocess.run(  # noqa: S603
        [
            shutil.which("git") or "/usr/bin/git",
            "show",
            f"{receipt['remote_issue_commit_sha']}:{ledger_path}",
        ],
        check=True,
        capture_output=True,
    ).stdout
    if content.splitlines(keepends=True).count(canonical_line(forecast)) != 1:
        raise ValueError("forecast absent or duplicated in receipt's remote commit")


def make_receipt(
    forecast: dict[str, Any],
    *,
    remote_sha: str,
    remote_content: bytes,
    confirmed_at: datetime,
    run_id: str,
) -> dict[str, Any]:
    if remote_content.splitlines(keepends=True).count(canonical_line(forecast)) != 1:
        raise ValueError("remote ledger does not contain exactly one canonical forecast")
    receipt = {
        key: forecast[key]
        for key in ("version", "origin_utc", "issued_at_utc", "target_5m_close_utc")
    }
    receipt.update(
        first_party_remote_confirmed_at_utc=confirmed_at.isoformat().replace("+00:00", "Z"),
        remote_issue_commit_sha=remote_sha,
        forecast_canonical_line_sha256=canonical_digest(forecast),
        workflow_run_id=run_id,
        remote_ref_was_fetched_and_compared=True,
        independent_time_witness=False,
    )
    validate_receipt(forecast, receipt)
    return receipt


def validate_score_match(forecast: dict[str, Any], score: dict[str, Any]) -> None:
    """Validate identity, observed maturity, and recompute losses from stored actuals."""
    import math

    for key in (
        "version",
        "origin_utc",
        "issued_at_utc",
        "target_5m_bar_open_utc",
        "target_5m_close_utc",
    ):
        if forecast[key] != score.get(key):
            raise ValueError(f"score mismatch: {key}")
    if at(score["target_observed_at_utc"]) < at(forecast["target_5m_close_utc"]):
        raise ValueError("score observed before target maturity")
    if forecast["version"] == "btc4h-continuous-v2-ridge100":
        if score.get("forecast_canonical_line_sha256") != canonical_digest(forecast):
            raise ValueError("score forecast SHA256 mismatch")
    actual = score["actual_close_usd"]
    ref = forecast["origin_reference_close_usd"]
    if isinstance(actual, bool) or not math.isfinite(actual) or actual <= 0:
        raise ValueError("invalid score actual")
    prices = forecast["price_forecasts_usd"]
    models = {"volume_interaction", "price_plus_volume", "price_only", "persistence"}
    if set(prices) != models or set(score["absolute_log_price_errors"]) != models:
        raise ValueError("score missing model comparators")
    for name, price in prices.items():
        expected = abs(math.log(price / actual))
        if not math.isclose(score["absolute_log_price_errors"][name], expected, abs_tol=1e-14):
            raise ValueError("score error differs from recomputed loss")
        direction = (
            None
            if abs(math.log(price / ref)) <= 1e-12 or actual == ref
            else (price > ref) == (actual > ref)
        )
        if score["direction_correct_if_nonflat"].get(name) is not direction:
            raise ValueError("score direction differs from recomputed direction")


def require_issue_delivery(result, forecasts, receipts, ledger_path):
    """A green job or an unrelated old receipt is not evidence of this run's delivery."""
    status = result.get("research_status")
    if status not in ("issued", "already_issued") or (
        status == "issued" and result.get("newly_issued") != 1
    ):
        raise ValueError("NO_NEW_FORECAST: " + str(status))
    origin = result["origin_utc"]
    rows = [r for r in forecasts if r.get("origin_utc") == origin]
    witnesses = [r for r in receipts if r.get("origin_utc") == origin]
    if len(rows) != 1 or len(witnesses) != 1:
        raise ValueError("ISSUANCE_NOT_RECEIPT_VERIFIED")
    row = rows[0]
    lead = (at(row["target_5m_close_utc"]) - at(row["issued_at_utc"])).total_seconds()
    if not 14400 <= lead <= 14700:
        raise ValueError("NOT_A_GENUINE_FOUR_HOUR_FORECAST")
    verify_stored_receipt(row, witnesses[0], ledger_path)
    return status
