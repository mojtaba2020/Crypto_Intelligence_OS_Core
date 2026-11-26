"""Hourly hybrid regression, prospective scoring, and idempotency tests."""

import json
import math
from datetime import UTC, datetime, timedelta

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
    monkeypatch.setattr(hourly, "_utc_now", lambda: now)
    first = hourly.run(now, ledger, report, scores)
    assert {row["horizon_hours"] for row in first["issued"]} == {1, 2, 3, 4, 12, 24}
    assert first["newly_scored"] == 0
    assert hourly.run(now, ledger, report, scores)["issued"] == []
    assert len(hourly.ledger_rows(ledger)) == 6
    prior = {
        **first["issued"][0],
        "origin_hour_utc": (now - timedelta(hours=3)).replace(minute=0).isoformat(),
        "target_hour_utc": (now - timedelta(hours=2)).replace(minute=0).isoformat(),
        "target_close_utc": (now - timedelta(hours=1)).replace(minute=0).isoformat(),
        "issued_at_utc": (now - timedelta(hours=2, minutes=50)).isoformat(),
    }
    with ledger.open("a", encoding="utf-8") as output:
        output.write(json.dumps(prior) + "\n")
    assert hourly.run(now, ledger, report, scores)["newly_scored"] == 1
    assert hourly.run(now, ledger, report, scores)["newly_scored"] == 0
    assert len(hourly.ledger_rows(scores)) == 1


@pytest.mark.parametrize(("horizon", "seconds"), [(2, 6643), (3, 10243)])
def test_receipt_and_maturity(tmp_path, monkeypatch, horizon, seconds):
    cutoff = datetime(2026, 9, 20, 12, 9, tzinfo=UTC)
    issued = cutoff + timedelta(seconds=17)
    monkeypatch.setattr(hourly, "HORIZONS", (horizon,))
    monkeypatch.setattr(hourly, "_utc_now", lambda: issued)
    monkeypatch.setattr(hourly, "fetch", _candles)
    ledger = tmp_path / "forecasts.jsonl"
    report = tmp_path / "report.json"
    first = hourly.run(cutoff, ledger, report)
    (receipt,) = first["issued"]
    target = datetime.fromisoformat(receipt["target_close_utc"])
    assert receipt["issued_at_utc"] == issued.isoformat()
    assert target == cutoff.replace(hour=12 + horizon, minute=0)
    assert receipt["issue_to_target_seconds"] == seconds
    assert hourly.run(cutoff, ledger, report)["issued"] == []
    assert hourly.ledger_rows(ledger) == [receipt]

    # Even if the data provider returned a target price early, reject it.
    monkeypatch.setattr(hourly, "fetch", lambda _: _candles(target))
    assert hourly.run(target - timedelta(microseconds=1), ledger, report)["newly_scored"] == 0
    assert hourly.run(target, ledger, report)["newly_scored"] == 1
    assert hourly.run(target, ledger, report)["newly_scored"] == 0
    (score,) = hourly.ledger_rows(tmp_path / "hourly_scores.jsonl")
    assert score["horizon_hours"] == receipt["horizon_hours"] == horizon
    assert score["target_close_utc"] == target.isoformat()
    actual = _candles(target)[-1][1]
    assert score["model_absolute_error_usd"] == abs(receipt["forecast_usd"] - actual)
    assert score["persistence_absolute_error_usd"] == abs(receipt["persistence_usd"] - actual)


@pytest.mark.parametrize("horizon", [2, 3])
def test_never_backfills_stale_origin(tmp_path, monkeypatch, horizon):
    cutoff = datetime(2026, 9, 20, 12, 59, 59, tzinfo=UTC)
    monkeypatch.setattr(hourly, "HORIZONS", (horizon,))
    monkeypatch.setattr(hourly, "fetch", _candles)
    monkeypatch.setattr(hourly, "_utc_now", lambda: cutoff + timedelta(seconds=1))
    ledger = tmp_path / "forecasts.jsonl"
    assert hourly.run(cutoff, ledger, tmp_path / "report.json")["issued"] == []
    assert not ledger.exists()
