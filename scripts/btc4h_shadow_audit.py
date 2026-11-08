"""Audit BTC 4h shadow research without hiding missed or altered predictions.

This is a first-party, internal consistency audit, NOT independent evidence
of the GitHub commit's first-publication time or exchange data provenance.
A successful audit is NOT evidence of profitable or accurate forecasting.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from scripts.btc4h_shadow_forward import (
    MODEL_NAMES,
    VERSION,
    _read_jsonl,
    calculate_score,
    in_issue_window,
    iso,
    origin_at,
    utc,
)

FOUR_HOURS = timedelta(hours=4)
ISSUE_DEADLINE = timedelta(minutes=15)


def _parse_utc(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("ledger timestamp must be an ISO UTC string")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("malformed ledger timestamp") from exc
    return utc(dt)


def _positive_finite(value: Any) -> bool:
    return (
        isinstance(value, (float, int))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    )


def _fingerprint(rows: list[dict[str, Any]]) -> str:
    payload = "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"
        for row in rows
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _validate_forecast(row: dict[str, Any], as_of: datetime) -> datetime:
    if (
        not isinstance(row, dict)
        or row.get("version") != VERSION
        or row.get("research_only") is not True
        or row.get("not_a_trade") is not True
        or row.get("independent_source_witness") is not False
    ):
        raise ValueError("unrecognized or unaudited shadow forecast version")
    origin = _parse_utc(row["origin_utc"])
    issued = _parse_utc(row["issued_at_utc"])
    if (
        origin_at(origin) != origin
        or origin_at(issued) != origin
        or not in_issue_window(issued)
        or issued > as_of
    ):
        raise ValueError("forecast origin, actual issuance time or cutoff invalid")
    target_open = _parse_utc(row["target_5m_bar_open_utc"])
    target_close = _parse_utc(row["target_5m_close_utc"])
    if (
        target_open != origin + timedelta(hours=4, minutes=10)
        or target_close != target_open + timedelta(minutes=5)
        or issued >= target_close
    ):
        raise ValueError("wrong five-minute outcome interval")
    for key in ("hourly_data_collected_at_utc", "target_training_data_collected_at_utc"):
        observed = _parse_utc(row[key])
        if not origin <= observed <= issued:
            raise ValueError("source timestamp is outside real forward issuance window")
    reference = row["origin_reference_close_usd"]
    if not _positive_finite(reference):
        raise ValueError("invalid reference price")
    prices = row["price_forecasts_usd"]
    returns = row["return_forecasts"]
    if set(prices) != set(MODEL_NAMES) or set(returns) != set(MODEL_NAMES):
        raise ValueError("missing or unexpected forecast comparators")
    for name in MODEL_NAMES:
        price = prices[name]
        value = returns[name]
        if not _positive_finite(price) or not math.isfinite(value):
            raise ValueError("nonfinite model price or return")
        if not math.isclose(math.log(price / reference), value, abs_tol=1e-12):
            raise ValueError("recorded forecast price conflicts with predicted return")
    if prices["persistence"] != reference or returns["persistence"] != 0:
        raise ValueError("Persistence control was altered")
    if (
        not isinstance(row["mature_historical_training_examples"], int)
        or row["mature_historical_training_examples"] < 30
    ):
        raise ValueError("invalid training sample count")
    for key in ("source_hourly_digest_sha256", "source_training_target_digest_sha256"):
        digest = row[key]
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(c not in "0123456789abcdef" for c in digest)
        ):
            raise ValueError("missing or malformed source snapshot hash")
    return origin


def audit_shadow_ledgers(
    issued_rows: list[dict[str, Any]],
    scored_rows: list[dict[str, Any]],
    *,
    study_start_utc: datetime,
    study_end_exclusive_utc: datetime,
    as_of_utc: datetime,
) -> dict[str, Any]:
    """Validate issue/score pairing and report every due four-hour origin.

    The start of the study MUST be chosen before reviewing its results.
    A missed scheduled slot is NOT interpolated or relabeled as a forecast.
    """
    for moment in (study_start_utc, study_end_exclusive_utc, as_of_utc):
        utc(moment)
    if (
        origin_at(study_start_utc) != study_start_utc
        or origin_at(study_end_exclusive_utc) != study_end_exclusive_utc
        or not study_start_utc < study_end_exclusive_utc
        or study_end_exclusive_utc - study_start_utc > timedelta(days=366)
        or study_start_utc > as_of_utc
    ):
        raise ValueError("invalid predeclared four-hour study interval")
    originals: dict[str, dict[str, Any]] = {}
    for row in issued_rows:
        origin = _validate_forecast(row, as_of_utc)
        key = iso(origin)
        if key in originals:
            raise ValueError("duplicate issued origin")
        originals[key] = row

    resolved: dict[str, dict[str, Any]] = {}
    for score in scored_rows:
        if (
            not isinstance(score, dict)
            or score.get("version") != VERSION
            or score.get("research_only") is not True
        ):
            raise ValueError("unrecognized score version")
        key = score["origin_utc"]
        if key not in originals:
            raise ValueError("orphan score has no original issued forecast")
        if key in resolved:
            raise ValueError("duplicate score for the same original forecast")
        received = _parse_utc(score["target_observed_at_utc"])
        if received > as_of_utc:
            raise ValueError("score reports an outcome not yet received")
        expected = calculate_score(
            originals[key],
            actual=score["actual_close_usd"],
            target_received_at=received,
        )
        for field in (
            "version",
            "origin_utc",
            "issued_at_utc",
            "target_5m_bar_open_utc",
            "target_5m_close_utc",
            "target_observed_at_utc",
            "research_only",
            "direction_correct_if_nonflat",
        ):
            if score.get(field) != expected[field]:
                raise ValueError(f"stored score conflicts with original issuance: {field}")
        if not math.isclose(
            score["actual_log_return"], expected["actual_log_return"], abs_tol=1e-12
        ):
            raise ValueError("stored actual return conflicts with observed price")
        loss = score["absolute_log_price_errors"]
        if set(loss) != set(MODEL_NAMES):
            raise ValueError("stored score has missing/extra comparators")
        for name in MODEL_NAMES:
            if (
                not isinstance(loss[name], (int, float))
                or isinstance(loss[name], bool)
                or not math.isfinite(loss[name])
                or not math.isclose(
                    loss[name], expected["absolute_log_price_errors"][name], abs_tol=1e-12
                )
            ):
                raise ValueError("stored forecast error was altered")
        resolved[key] = score

    scheduled = 0
    due = 0
    issued_due = 0
    mature_due = 0
    scored_due = 0
    pending_due = 0
    missing_due = 0
    mappable = []
    cursor = study_start_utc
    while cursor < study_end_exclusive_utc:
        scheduled += 1
        key = iso(cursor)
        issued = originals.get(key)
        if cursor + ISSUE_DEADLINE <= as_of_utc:
            due += 1
            if issued is None:
                missing_due += 1
            else:
                issued_due += 1
                target_close = cursor + timedelta(hours=4, minutes=15)
                if target_close <= as_of_utc:
                    mature_due += 1
                    score = resolved.get(key)
                    if score is not None:
                        scored_due += 1
                        mappable.append(score)
                else:
                    pending_due += 1
        cursor += FOUR_HOURS

    losses = {
        name: (
            math.fsum(row["absolute_log_price_errors"][name] for row in mappable) / len(mappable)
            if mappable
            else None
        )
        for name in MODEL_NAMES
    }
    baseline = losses["persistence"]
    primary = losses["volume_interaction"]
    gain = (
        100.0 * (baseline - primary) / baseline
        if baseline is not None and primary is not None and baseline > 0
        else None
    )
    nonflat = [
        row["direction_correct_if_nonflat"]["volume_interaction"]
        for row in mappable
        if row["direction_correct_if_nonflat"]["volume_interaction"] is not None
    ]
    accuracy = 100.0 * sum(x is True for x in nonflat) / len(nonflat) if nonflat else None
    return {
        "status": "FIRST_PARTY_INTERNAL_AUDIT_ONLY",
        "version": VERSION,
        "study_start_utc": iso(study_start_utc),
        "study_end_exclusive_utc": iso(study_end_exclusive_utc),
        "as_of_utc": iso(as_of_utc),
        "scheduled_origins_in_window": scheduled,
        "finalized_issue_slots": due,
        "not_yet_due_issue_slots": scheduled - due,
        "issued_in_finalized_slots": issued_due,
        "missed_finalized_slots": missing_due,
        "issue_delivery_rate_pct": 100 * issued_due / due if due else None,
        "issued_origins_with_mature_targets": mature_due,
        "matured_origins_already_scored": scored_due,
        "unscored_matured_origins": mature_due - scored_due,
        "issued_but_targets_not_yet_mature": pending_due,
        "mean_absolute_log_price_error": losses,
        "candidate_gain_vs_persistence_pct": gain,
        "candidate_direction_nonflat_correct": sum(x is True for x in nonflat),
        "candidate_direction_nonflat_assessed": len(nonflat),
        "candidate_direction_nonflat_accuracy_pct": accuracy,
        "issue_ledger_snapshot_sha256": _fingerprint(issued_rows),
        "score_ledger_snapshot_sha256": _fingerprint(scored_rows),
        "independently_witnessed_first_publication": False,
        "validated_alpha": False,
        "research_only": True,
        "note": (
            "Missed slots include failed or nonattempted runs, not model forecasts. "
            "Hashes prove only consistency of the currently supplied snapshot; "
            "GitHub commit timing/source vintage requires separate verification."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--scores", type=Path, required=True)
    parser.add_argument("--receipts", type=Path, required=False)
    parser.add_argument("--study-start", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--study-end", help="UTC aligned exclusive end; defaults to the next 4h boundary"
    )
    args = parser.parse_args()
    now = datetime.now(UTC)
    start = _parse_utc(args.study_start)
    end = _parse_utc(args.study_end) if args.study_end else origin_at(now) + FOUR_HOURS
    issued = _read_jsonl(args.ledger)
    scores = _read_jsonl(args.scores)
    result = audit_shadow_ledgers(
        issued,
        scores,
        study_start_utc=start,
        study_end_exclusive_utc=end,
        as_of_utc=now,
    )
    if args.receipts is not None:
        # Import here to avoid a module-level import cycle:
        # publication receipts reuse _validate_forecast from this module.
        from scripts.btc4h_publication_receipts import validate_receipts

        result.update(
            validate_receipts(issued, _read_jsonl(args.receipts), as_of_utc=now)
        )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
