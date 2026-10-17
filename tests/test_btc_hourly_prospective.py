"""Hourly hybrid regression, prospective scoring, and idempotency tests."""

import json
import math
from datetime import UTC, datetime, timedelta, timezone

import pytest
from scripts import btc_hourly_prospective as hourly


def _candles(now):
    end = now.replace(minute=0, second=0, microsecond=0)
    return [
        (end - timedelta(hours=720 - index), 50000 * math.exp(index * 0.0001))
        for index in range(720)
    ]


def test_training_uses_resolved_labels_and_returns_finite_prediction():
    now = datetime(2026, 9, 20, 12, 9, tzinfo=UTC)
    candles = _candles(now)
    for horizon in hourly.HORIZONS:
        signal, blend, examples = hourly.train(candles, horizon)
        assert math.isfinite(signal)
        assert blend in (0.0, 0.25, 0.5, 0.75, 1.0)
        assert examples == 720 - 168 - horizon


def test_hourly_issuance_scoring_and_idempotency(tmp_path, monkeypatch):
    now = datetime(2026, 9, 20, 12, 9, tzinfo=UTC)
    candles = _candles(now)
    monkeypatch.setattr(hourly, "fetch", lambda _now: candles)
    ledger = tmp_path / "forecasts.jsonl"
    scores = tmp_path / "scores.jsonl"
    report = tmp_path / "report.json"

    def postfit_clock():
        return now + timedelta(seconds=2)

    first = hourly.run(now, ledger, report, scores, issue_clock=postfit_clock)
    assert len(first["issued"]) == 4
    assert first["newly_scored"] == 0
    assert hourly.run(now, ledger, report, scores, issue_clock=postfit_clock)["issued"] == []
    assert len(hourly.ledger_rows(ledger)) == 4
    prior = {
        **first["issued"][0],
        "origin_hour_utc": (now - timedelta(hours=3)).replace(minute=0).isoformat(),
        "target_hour_utc": (now - timedelta(hours=2)).replace(minute=0).isoformat(),
        "target_close_utc": (now - timedelta(hours=1)).replace(minute=0).isoformat(),
        "issued_at_utc": (now - timedelta(hours=2, minutes=50)).isoformat(),
    }
    with ledger.open("a", encoding="utf-8") as output:
        output.write(json.dumps(prior) + "\n")
    assert hourly.run(now, ledger, report, scores, issue_clock=postfit_clock)["newly_scored"] == 1
    assert hourly.run(now, ledger, report, scores, issue_clock=postfit_clock)["newly_scored"] == 0
    assert len(hourly.ledger_rows(scores)) == 1


def test_postfit_timestamp_is_sampled_only_after_all_models_finish(tmp_path, monkeypatch):
    now = datetime(2026, 9, 20, 12, 9, tzinfo=UTC)
    candles = _candles(now)
    monkeypatch.setattr(hourly, "fetch", lambda _now: candles)
    fitted = []
    original_train = hourly.train

    def checked_train(rows, horizon):
        fitted.append(horizon)
        return original_train(rows, horizon)

    def clock_after_fits():
        assert fitted == list(hourly.HORIZONS)
        return now + timedelta(seconds=7)

    monkeypatch.setattr(hourly, "train", checked_train)
    result = hourly.run(
        now, tmp_path / "hourly.jsonl", tmp_path / "report.json", issue_clock=clock_after_fits
    )
    expected = (now + timedelta(seconds=7)).isoformat()
    assert len(result["issued"]) == 4
    assert all(row["issued_at_utc"] == expected for row in result["issued"])


@pytest.mark.parametrize(
    "late",
    [
        datetime(2026, 9, 20, 13, tzinfo=UTC),
        datetime(2026, 9, 20, 13, 0, 1, tzinfo=UTC),
    ],
)
def test_late_postfit_issue_rejects_whole_batch_before_writing(tmp_path, monkeypatch, late):
    now = datetime(2026, 9, 20, 12, 9, tzinfo=UTC)
    monkeypatch.setattr(hourly, "fetch", lambda _now: _candles(now))
    ledger = tmp_path / "hourly.jsonl"
    with pytest.raises(ValueError, match="matured before postfit"):
        hourly.run(now, ledger, tmp_path / "report.json", issue_clock=lambda: late)
    assert not ledger.exists()


def test_postfit_clock_rollback_and_naive_timestamp_rejected(tmp_path, monkeypatch):
    now = datetime(2026, 9, 20, 12, 9, tzinfo=UTC)
    monkeypatch.setattr(hourly, "fetch", lambda _now: _candles(now))
    for clock, error in (
        (lambda: now - timedelta(seconds=1), "cannot precede"),
        (lambda: datetime(2026, 9, 20, 12, 9), "timezone-aware"),
    ):
        with pytest.raises(ValueError, match=error):
            hourly.run(now, tmp_path / "hourly.jsonl", tmp_path / "report.json", issue_clock=clock)


def test_postfit_guard_normalizes_offset_and_rejects_empty_batches():
    now = datetime(2026, 9, 20, 12, 9, tzinfo=UTC)
    issued = now + timedelta(seconds=3)
    target = now + timedelta(hours=1)
    shifted = issued.astimezone(timezone(timedelta(hours=-5)))
    assert hourly.validate_postfit_issuance(now, shifted, [target]) == issued.isoformat()
    with pytest.raises(ValueError, match="Empty forecast batch"):
        hourly.validate_postfit_issuance(now, issued, [])
