"""Adversarial no-network tests for first-party BTC4h Git confirmation receipts.

The tests deliberately do NOT assert independent GitHub server timestamping.
"""

import copy
import json
import math
from datetime import UTC, datetime, timedelta

import pytest
from scripts.btc4h_publication_receipts import (
    make_issue_receipt,
    validate_receipts,
    write_latest_receipt,
)
from scripts.btc4h_shadow_forward import MODEL_NAMES, VERSION, iso


def _issue():
    origin = datetime(2026, 11, 8, 12, tzinfo=UTC)
    returns = {
        "volume_interaction": 0.002,
        "price_plus_volume": 0.001,
        "price_only": -0.001,
        "persistence": 0.0,
    }
    reference = 65000.0
    return {
        "version": VERSION,
        "origin_utc": iso(origin),
        "issued_at_utc": iso(origin + timedelta(minutes=12)),
        "hourly_data_collected_at_utc": iso(origin + timedelta(minutes=11)),
        "target_training_data_collected_at_utc": iso(origin + timedelta(minutes=11, seconds=10)),
        "target_5m_bar_open_utc": iso(origin + timedelta(hours=4, minutes=10)),
        "target_5m_close_utc": iso(origin + timedelta(hours=4, minutes=15)),
        "origin_reference_close_usd": reference,
        "price_forecasts_usd": {
            name: reference * math.exp(returns[name]) for name in MODEL_NAMES
        },
        "return_forecasts": returns,
        "mature_historical_training_examples": 59,
        "source_hourly_digest_sha256": "a" * 64,
        "source_training_target_digest_sha256": "b" * 64,
        "research_only": True,
        "not_a_trade": True,
        "independent_source_witness": False,
    }


def _stamp(minutes=13):
    return datetime(2026, 11, 8, 12, tzinfo=UTC) + timedelta(minutes=minutes)


def _receipt():
    return make_issue_receipt(
        _issue(),
        remote_commit_sha="c" * 40,
        fetched_remote_sha="c" * 40,
        confirmed_at_utc=_stamp(),
        run_id="123456",
    )


def test_matched_pre_target_remote_sha_generates_receipt_not_alpha():
    receipt = _receipt()
    assert receipt["origin_utc"] == _issue()["origin_utc"]
    assert receipt["remote_issue_commit_sha"] == "c" * 40
    assert len(receipt["forecast_canonical_line_sha256"]) == 64
    assert receipt["remote_ref_was_fetched_and_compared"] is True
    assert receipt["independent_time_witness"] is False
    summary = validate_receipts([_issue()], [receipt], as_of_utc=_stamp(20))
    assert summary["confirmed_remote_receipts"] == 1
    assert summary["unconfirmed_issued_forecasts"] == 0
    assert summary["independently_witnessed"] is False


def test_remote_publication_at_or_after_target_close_is_rejected():
    target_close = datetime(2026, 11, 8, 16, 15, tzinfo=UTC)
    for when in (target_close, target_close + timedelta(microseconds=1)):
        with pytest.raises(ValueError, match="before target closed"):
            make_issue_receipt(
                _issue(),
                remote_commit_sha="c" * 40,
                fetched_remote_sha="c" * 40,
                confirmed_at_utc=when,
                run_id="123",
            )


def test_remote_commit_mismatch_rejected_before_claiming_publication():
    with pytest.raises(ValueError, match="does not match"):
        make_issue_receipt(
            _issue(),
            remote_commit_sha="c" * 40,
            fetched_remote_sha="d" * 40,
            confirmed_at_utc=_stamp(),
            run_id="123",
        )


def test_self_issued_future_timestamp_and_unvalidated_sha_are_rejected():
    altered = _issue()
    altered["issued_at_utc"] = iso(_stamp(14))
    with pytest.raises(ValueError, match=r"issue|cutoff|invalid"):
        make_issue_receipt(
            altered,
            remote_commit_sha="c" * 40,
            fetched_remote_sha="c" * 40,
            confirmed_at_utc=_stamp(13),
            run_id="123",
        )
    with pytest.raises(ValueError, match="40-character"):
        make_issue_receipt(
            _issue(),
            remote_commit_sha="not-an-actual-commit",
            fetched_remote_sha="not-an-actual-commit",
            confirmed_at_utc=_stamp(),
            run_id="123",
        )


def test_missing_or_forged_receipts_fail_closed():
    with pytest.raises(ValueError, match="missing timely"):
        validate_receipts([_issue()], [], as_of_utc=_stamp(20))
    original = _receipt()
    corrupted = copy.deepcopy(original)
    corrupted["forecast_canonical_line_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="forecast hash mismatch"):
        validate_receipts([_issue()], [corrupted], as_of_utc=_stamp(20))
    forged = copy.deepcopy(original)
    forged["independent_time_witness"] = True
    with pytest.raises(ValueError, match="independent witness"):
        validate_receipts([_issue()], [forged], as_of_utc=_stamp(20))


def test_duplicate_orphan_and_late_claimed_receipts_fail_closed():
    good = _receipt()
    with pytest.raises(ValueError, match="duplicate publication"):
        validate_receipts([_issue()], [good, good], as_of_utc=_stamp(20))
    orphan = copy.deepcopy(good)
    orphan["origin_utc"] = iso(_stamp(20))
    with pytest.raises(ValueError, match="orphan"):
        validate_receipts([_issue()], [orphan], as_of_utc=_stamp(20))
    late = copy.deepcopy(good)
    late["first_party_remote_confirmed_at_utc"] = iso(_stamp(16 + 4 * 60))
    with pytest.raises(ValueError, match=r"future-dated|pre-target"):
        validate_receipts([_issue()], [late], as_of_utc=_stamp(20))


def test_receipt_ledger_appends_once_without_overwriting_old_one(tmp_path):
    issue_file = tmp_path / "issues.jsonl"
    receipts_file = tmp_path / "receipts.jsonl"
    issue_file.write_text(json.dumps(_issue()) + "\n", encoding="utf-8")
    receipt = write_latest_receipt(
        issue_file,
        receipts_file,
        remote_commit_sha="c" * 40,
        confirmed_at_utc=_stamp(),
        run_id="123",
    )
    assert receipt["origin_utc"] == _issue()["origin_utc"]
    with pytest.raises(ValueError, match="already exists"):
        write_latest_receipt(
            issue_file,
            receipts_file,
            remote_commit_sha="c" * 40,
            confirmed_at_utc=_stamp(14),
            run_id="123",
        )
    assert len(receipts_file.read_text(encoding="utf-8").splitlines()) == 1
