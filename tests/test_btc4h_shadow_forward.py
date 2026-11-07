"""No-network tests of forward-only 4h shadow issuance and objective maturity."""

import json
import math
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from scripts import btc4h_shadow_forward as shadow


def _fixture():
    origin = datetime(2026, 11, 8, 12, tzinfo=UTC)
    hourly = {}
    first_hour = origin - timedelta(days=shadow.HISTORY_DAYS, hours=25)
    hour = first_hour
    n = 0
    while hour < origin:
        price = 65000.0 * math.exp(0.0001 * n + 0.007 * math.sin(n / 16))
        vol = 15.0 + 3 * (1 + math.sin(n / 11))
        hourly[hour] = (price, vol)
        hour += timedelta(hours=1)
        n += 1
    targets = {}
    historical = origin - timedelta(days=shadow.HISTORY_DAYS)
    while historical <= origin - timedelta(hours=8):
        t = historical + timedelta(hours=4, minutes=10)
        targets[t] = hourly[historical - timedelta(hours=1)][0] * math.exp(
            0.001 * math.sin((historical - origin).total_seconds() / 40000)
        )
        historical += timedelta(hours=4)
    return origin, hourly, targets


def _issue():
    origin, hourly, targets = _fixture()
    row = shadow.calculate_issue(
        issued_at=origin + timedelta(minutes=12),
        hourly_fetched_at=origin + timedelta(minutes=11),
        target_fetched_at=origin + timedelta(minutes=11, seconds=20),
        hourly=hourly,
        closed_targets=targets,
        code_sha="a" * 40,
    )
    return origin, hourly, targets, row


def test_forecast_is_a_real_future_target_with_four_model_controls():
    origin, hourly, targets, row = _issue()
    assert row["origin_utc"] == shadow.iso(origin)
    assert row["target_5m_close_utc"] == shadow.iso(origin + timedelta(hours=4, minutes=15))
    assert row["issued_at_utc"] == shadow.iso(origin + timedelta(minutes=12))
    assert row["mature_historical_training_examples"] == 59
    assert row["missing_training_hourly_origins"] == 0
    assert row["missing_training_target_origins"] == 0
    assert row["price_forecasts_usd"]["persistence"] == hourly[origin - timedelta(hours=1)][0]
    assert set(row["price_forecasts_usd"]) == set(shadow.MODEL_NAMES)
    assert all(math.isfinite(x) and x > 0 for x in row["price_forecasts_usd"].values())
    assert row["not_a_trade"] and not row["independent_source_witness"]


def test_early_and_late_issuance_rejected_without_backdating():
    origin, hourly, targets = _fixture()
    for minute in (9, 16):
        with pytest.raises(ValueError, match="MISS_ISSUE_WINDOW"):
            shadow.calculate_issue(
                issued_at=origin + timedelta(minutes=minute),
                hourly_fetched_at=origin + timedelta(minutes=8),
                target_fetched_at=origin + timedelta(minutes=8),
                hourly=hourly,
                closed_targets=targets,
            )
    assert not shadow.in_issue_window(origin - timedelta(minutes=1))
    assert not shadow.in_issue_window(origin + timedelta(minutes=16))


def test_source_received_after_issue_rejected():
    origin, hourly, targets = _fixture()
    with pytest.raises(ValueError, match="received by actual issue"):
        shadow.calculate_issue(
            issued_at=origin + timedelta(minutes=12),
            hourly_fetched_at=origin + timedelta(minutes=12, seconds=1),
            target_fetched_at=origin + timedelta(minutes=11),
            hourly=hourly,
            closed_targets=targets,
        )


def test_future_target_cannot_be_used_as_training_label():
    origin, hourly, targets = _fixture()
    target_never_mature_in_issue_window = origin + timedelta(minutes=10)
    targets[target_never_mature_in_issue_window] = 100000000.0
    reference = _issue()[3]
    issue = shadow.calculate_issue(
        issued_at=origin + timedelta(minutes=12),
        hourly_fetched_at=origin + timedelta(minutes=11),
        target_fetched_at=origin + timedelta(minutes=11, seconds=20),
        hourly=hourly,
        closed_targets=targets,
        code_sha="a" * 40,
    )
    assert issue["return_forecasts"] == reference["return_forecasts"]
    assert issue["mature_historical_training_examples"] == 59


def test_missing_target_is_skipped_not_filled_by_future():
    origin, hourly, targets = _fixture()
    targets.pop(min(targets))
    row = shadow.calculate_issue(
        issued_at=origin + timedelta(minutes=12),
        hourly_fetched_at=origin + timedelta(minutes=11),
        target_fetched_at=origin + timedelta(minutes=11, seconds=20),
        hourly=hourly,
        closed_targets=targets,
    )
    assert row["mature_historical_training_examples"] == 58
    assert row["missing_training_target_origins"] == 1


def test_current_hourly_candle_missing_fails_closed():
    origin, hourly, targets = _fixture()
    hourly.pop(origin - timedelta(hours=1))
    with pytest.raises(ValueError, match="current 25 hourly"):
        shadow.calculate_issue(
            issued_at=origin + timedelta(minutes=12),
            hourly_fetched_at=origin + timedelta(minutes=11),
            target_fetched_at=origin + timedelta(minutes=11, seconds=20),
            hourly=hourly,
            closed_targets=targets,
        )


def test_score_before_target_close_is_impossible():
    origin, _, _, forecast = _issue()
    with pytest.raises(ValueError, match="pre-target"):
        shadow.calculate_score(
            forecast, actual=66000,
            target_received_at=origin + timedelta(hours=4, minutes=14),
        )
    score = shadow.calculate_score(
        forecast, actual=66000,
        target_received_at=origin + timedelta(hours=4, minutes=15, seconds=5),
    )
    assert score["target_observed_at_utc"] == shadow.iso(
        origin + timedelta(hours=4, minutes=15, seconds=5)
    )
    assert score["absolute_log_price_errors"]["persistence"] >= 0
    assert score["direction_correct_if_nonflat"]["persistence"] is None
    assert score["research_only"]


def test_score_does_not_accept_forged_late_issue_or_collection():
    origin, _, _, row = _issue()
    altered = dict(row)
    altered["issued_at_utc"] = shadow.iso(origin + timedelta(hours=4, minutes=16))
    with pytest.raises(ValueError, match="pre-target"):
        shadow.calculate_score(
            altered,
            actual=65000,
            target_received_at=origin + timedelta(hours=5),
        )
    altered = dict(row)
    altered["hourly_data_collected_at_utc"] = shadow.iso(origin + timedelta(minutes=13))
    with pytest.raises(ValueError, match="source evidence"):
        shadow.calculate_score(
            altered, actual=65000,
            target_received_at=origin + timedelta(hours=5),
        )


def test_ledger_append_replay_idempotent_jsonl(tmp_path):
    _, _, _, row = _issue()
    p = tmp_path / "shadow.jsonl"
    shadow._append(p, row)
    assert shadow._read_jsonl(p) == [row]
    with p.open("a") as out:
        out.write(json.dumps({"x": 1}) + "\n")
    assert len(shadow._read_jsonl(p)) == 2
    with p.open("a") as out:
        out.write("not-json\n")
    with pytest.raises(json.JSONDecodeError):
        shadow._read_jsonl(p)


def test_live_pipeline_issues_once_and_scores_only_after_future_target(tmp_path, monkeypatch):
    origin, hourly, targets = _fixture()
    calls = []

    def fetch_hourly(*_args):
        calls.append("hourly")
        return hourly

    def fetch_five_minute(start, end, *, granularity):
        assert granularity == 300
        if end - start > timedelta(days=1):
            calls.append("historical_training_targets")
            return targets
        calls.append("actual_future_target")
        return {start: 66000.0}

    monkeypatch.setattr(shadow, "fetch_public_hourly_close_volume", fetch_hourly)
    monkeypatch.setattr(shadow, "fetch_candles", fetch_five_minute)
    ledger = tmp_path / "issued.jsonl"
    scores = tmp_path / "scored.jsonl"
    report = tmp_path / "report.json"

    early = shadow.run_once(
        ledger=ledger, score_ledger=scores, report=report,
        clock=lambda: origin + timedelta(minutes=9),
    )
    assert early["research_status"] == "MISSED_ISSUE_WINDOW"
    assert early["newly_issued"] == 0
    assert not calls

    on_time = shadow.run_once(
        ledger=ledger, score_ledger=scores, report=report,
        clock=lambda: origin + timedelta(minutes=11),
    )
    assert on_time["research_status"] == "ISSUED_BEFORE_TARGET"
    assert on_time["newly_issued"] == 1
    assert on_time["newly_scored"] == 0
    assert calls == ["hourly", "historical_training_targets"]

    duplicate = shadow.run_once(
        ledger=ledger, score_ledger=scores, report=report,
        clock=lambda: origin + timedelta(minutes=11),
    )
    assert duplicate["research_status"] == "ALREADY_ISSUED"
    assert duplicate["newly_issued"] == 0
    assert duplicate["newly_scored"] == 0
    assert calls == ["hourly", "historical_training_targets"]

    later = shadow.run_once(
        ledger=ledger, score_ledger=scores, report=report,
        clock=lambda: origin + timedelta(hours=8, minutes=20),
    )
    assert later["research_status"] == "MISSED_ISSUE_WINDOW"
    assert later["newly_issued"] == 0
    assert later["newly_scored"] == 1
    assert calls[-1] == "actual_future_target"
    assert len(shadow._read_jsonl(ledger)) == 1
    assert len(shadow._read_jsonl(scores)) == 1

    scored_again = shadow.run_once(
        ledger=ledger, score_ledger=scores, report=report,
        clock=lambda: origin + timedelta(hours=8, minutes=20),
    )
    assert scored_again["newly_scored"] == 0
    assert len(shadow._read_jsonl(scores)) == 1


def test_fetch_finishing_after_window_must_not_issue(tmp_path, monkeypatch):
    origin, hourly, targets = _fixture()
    monkeypatch.setattr(
        shadow, "fetch_public_hourly_close_volume", lambda *_args: hourly
    )
    monkeypatch.setattr(
        shadow, "fetch_candles", lambda *_args, **_kwargs: targets
    )
    ticks = iter([
        origin + timedelta(minutes=11),
        origin + timedelta(minutes=11, seconds=30),
        origin + timedelta(minutes=15, seconds=1),
        origin + timedelta(minutes=15, seconds=1),
    ])
    result = shadow.run_once(
        ledger=tmp_path / "issued.jsonl",
        score_ledger=tmp_path / "scores.jsonl",
        report=tmp_path / "run.json",
        clock=lambda: next(ticks),
    )
    assert result["research_status"] == "MISSED_ISSUE_WINDOW_AFTER_FETCH"
    assert result["newly_issued"] == 0
