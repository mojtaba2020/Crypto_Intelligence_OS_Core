"""Hourly hybrid regression, prospective scoring, and idempotency tests."""

import json
import math
from datetime import UTC, datetime, timedelta

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
    first = hourly.run(now, ledger, report, scores)
    assert len(first["issued"]) == 4
    assert first["newly_scored"] == 0
    assert hourly.run(now, ledger, report, scores)["issued"] == []
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
    assert hourly.run(now, ledger, report, scores)["newly_scored"] == 1
    assert hourly.run(now, ledger, report, scores)["newly_scored"] == 0
    assert len(hourly.ledger_rows(scores)) == 1
