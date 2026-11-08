"""No-network adversarial tests for all-slot future-forecast ledger audit."""

import copy
import math
from datetime import UTC, datetime, timedelta

import pytest

from scripts.btc4h_shadow_audit import audit_shadow_ledgers
from scripts.btc4h_shadow_forward import MODEL_NAMES, VERSION, calculate_score, iso


def _forecast(origin):
    ref = 65000.0
    values = {
        "volume_interaction": 0.01,
        "price_plus_volume": 0.005,
        "price_only": -0.002,
        "persistence": 0.0,
    }
    return {
        "version": VERSION,
        "origin_utc": iso(origin),
        "issued_at_utc": iso(origin + timedelta(minutes=12)),
        "hourly_data_collected_at_utc": iso(origin + timedelta(minutes=11)),
        "target_training_data_collected_at_utc": iso(origin + timedelta(minutes=11, seconds=15)),
        "target_5m_bar_open_utc": iso(origin + timedelta(hours=4, minutes=10)),
        "target_5m_close_utc": iso(origin + timedelta(hours=4, minutes=15)),
        "origin_reference_close_usd": ref,
        "return_forecasts": values,
        "price_forecasts_usd": {name: ref * math.exp(value) for name, value in values.items()},
        "mature_historical_training_examples": 59,
        "source_hourly_digest_sha256": "a" * 64,
        "source_training_target_digest_sha256": "b" * 64,
        "independent_source_witness": False,
        "research_only": True,
        "not_a_trade": True,
    }


def _context():
    start = datetime(2026, 11, 8, 0, tzinfo=UTC)
    first = _forecast(start)
    second = _forecast(start + timedelta(hours=4))
    result = calculate_score(
        first, actual=65400.0, target_received_at=start + timedelta(hours=4, minutes=20)
    )
    params = {
        "study_start_utc": start,
        "study_end_exclusive_utc": start + timedelta(hours=12),
        "as_of_utc": start + timedelta(hours=8, minutes=20),
    }
    return first, second, result, params


def test_count_missed_and_matured_unscored_origins_without_hiding_denominators():
    first, second, score, params = _context()
    summary = audit_shadow_ledgers([first, second], [score], **params)
    assert summary["scheduled_origins_in_window"] == 3
    assert summary["finalized_issue_slots"] == 3
    assert summary["issued_in_finalized_slots"] == 2
    assert summary["missed_finalized_slots"] == 1
    assert summary["issue_delivery_rate_pct"] == pytest.approx(200 / 3)
    assert summary["issued_origins_with_mature_targets"] == 2
    assert summary["matured_origins_already_scored"] == 1
    assert summary["unscored_matured_origins"] == 1
    assert summary["issued_but_targets_not_yet_mature"] == 0
    assert summary["candidate_direction_nonflat_assessed"] == 1
    assert summary["candidate_direction_nonflat_correct"] == 1
    assert summary["mean_absolute_log_price_error"]["persistence"] > 0
    assert not summary["validated_alpha"]
    assert not summary["independently_witnessed_first_publication"]


def test_future_not_due_slots_are_not_miscounted_as_missing():
    first, second, _score, params = _context()
    params["as_of_utc"] = params["study_start_utc"] + timedelta(minutes=13)
    with pytest.raises(ValueError, match="cutoff"):
        audit_shadow_ledgers([first, second], [], **params)
    result = audit_shadow_ledgers([first], [], **params)
    assert result["finalized_issue_slots"] == 0
    assert result["not_yet_due_issue_slots"] == 3
    assert result["missed_finalized_slots"] == 0


def test_empty_ledger_has_explicit_zeros_not_fabricated_skill():
    _first, _second, _score, params = _context()
    r = audit_shadow_ledgers([], [], **params)
    assert r["missed_finalized_slots"] == 3
    assert r["issued_in_finalized_slots"] == 0
    assert r["candidate_gain_vs_persistence_pct"] is None
    assert r["candidate_direction_nonflat_accuracy_pct"] is None


def test_modified_score_error_is_rejected_before_reporting_accuracy():
    first, _second, score, params = _context()
    bad = copy.deepcopy(score)
    bad["absolute_log_price_errors"]["volume_interaction"] = 0.0
    with pytest.raises(ValueError, match="forecast error was altered"):
        audit_shadow_ledgers([first], [bad], **params)


def test_modified_direction_is_rejected():
    first, _second, score, params = _context()
    bad = copy.deepcopy(score)
    bad["direction_correct_if_nonflat"]["volume_interaction"] = False
    with pytest.raises(ValueError, match="stored score conflicts"):
        audit_shadow_ledgers([first], [bad], **params)


def test_orphan_score_and_duplicate_scores_are_rejected():
    first, _second, score, params = _context()
    with pytest.raises(ValueError, match="orphan"):
        audit_shadow_ledgers([], [score], **params)
    with pytest.raises(ValueError, match="duplicate score"):
        audit_shadow_ledgers([first], [score, score], **params)


def test_duplicate_issuance_cannot_be_framed_as_two_forecasts():
    first, _second, _score, params = _context()
    with pytest.raises(ValueError, match="duplicate issued"):
        audit_shadow_ledgers([first, first], [], **params)


def test_changed_forecast_return_rejected_even_without_score():
    first, _second, _score, params = _context()
    bad = copy.deepcopy(first)
    bad["return_forecasts"]["volume_interaction"] += 0.0005
    with pytest.raises(ValueError, match="conflicts"):
        audit_shadow_ledgers([bad], [], **params)


def test_wrong_target_and_source_after_issue_rejected():
    first, _second, _score, params = _context()
    bad = copy.deepcopy(first)
    bad["target_5m_close_utc"] = iso(params["study_start_utc"] + timedelta(hours=4))
    with pytest.raises(ValueError, match="outcome interval"):
        audit_shadow_ledgers([bad], [], **params)
    bad = copy.deepcopy(first)
    bad["hourly_data_collected_at_utc"] = iso(
        params["study_start_utc"] + timedelta(minutes=14)
    )
    with pytest.raises(ValueError, match="source timestamp"):
        audit_shadow_ledgers([bad], [], **params)


def test_accounting_includes_one_pending_target_before_five_minute_close():
    first, second, _score, params = _context()
    params["as_of_utc"] = params["study_start_utc"] + timedelta(hours=4, minutes=20)
    result = audit_shadow_ledgers([first, second], [], **params)
    assert result["finalized_issue_slots"] == 2
    assert result["issued_but_targets_not_yet_mature"] == 1
    assert result["unscored_matured_origins"] == 1
    assert result["not_yet_due_issue_slots"] == 1


def test_score_comparators_are_fixed():
    first, _second, score, params = _context()
    bad = copy.deepcopy(score)
    bad["absolute_log_price_errors"].pop(next(iter(MODEL_NAMES)))
    with pytest.raises(ValueError, match="missing/extra"):
        audit_shadow_ledgers([first], [bad], **params)
