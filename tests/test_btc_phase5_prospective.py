"""Prospective forecasts cannot be issued on unfinished or stale data."""

import sqlite3
from datetime import UTC, date, datetime, timedelta

import pytest
from scripts import btc_phase5_prospective as phase5
from scripts.btc_phase5_prospective import issue, score


def _database(tmp_path):
    database = tmp_path / "prices.sqlite"
    start = date(2023, 1, 1)
    end = date(2026, 9, 19)
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE daily_price (day TEXT, price_usd REAL)")
        connection.executemany(
            "INSERT INTO daily_price VALUES (?, ?)",
            (
                ((start + timedelta(days=index)).isoformat(), 10000 + index * 10)
                for index in range((end - start).days + 1)
            ),
        )
    return database


def test_issue_is_idempotent_and_targets_are_future(tmp_path, monkeypatch):
    database = _database(tmp_path)
    ledger = tmp_path / "ledger.jsonl"
    now = datetime(2026, 9, 20, 12, tzinfo=UTC)
    monkeypatch.setattr(phase5, "_utc_now", lambda: now)
    created = issue(database, ledger, now=now)
    assert len(created) == 10
    assert all(date.fromisoformat(row["target_day"]) >= now.date() for row in created)
    assert issue(database, ledger, now=now) == []
    report = score(database, ledger, now=now)
    assert report["ledger_entries"] == 10
    assert set(report["by_horizon"]) == {"1", "2", "3", "7", "14", "21", "30", "90", "180", "365"}
    assert all(row["resolved_examples"] == 0 for row in report["by_horizon"].values())


def test_issue_rejects_unfinished_day_and_stale_archive(tmp_path):
    database = _database(tmp_path)
    ledger = tmp_path / "ledger.jsonl"
    with pytest.raises(ValueError, match="completed"):
        issue(database, ledger, now=datetime(2026, 9, 19, 12, tzinfo=UTC))
    with pytest.raises(ValueError, match="stale"):
        issue(database, ledger, now=datetime(2026, 9, 23, 12, tzinfo=UTC))


def test_two_day_receipt_and_maturity(tmp_path, monkeypatch):
    database = _database(tmp_path)
    ledger = tmp_path / "ledger.jsonl"
    start = datetime(2026, 9, 20, 11, tzinfo=UTC)
    issued = start + timedelta(seconds=17)
    monkeypatch.setattr(phase5, "_utc_now", lambda: issued)
    (receipt,) = issue(database, ledger, now=start, horizons=(2, 2))
    assert issue(database, ledger, now=start, horizons=(2,)) == []
    assert phase5.load_ledger(ledger) == [receipt]
    target = datetime(2026, 9, 22, tzinfo=UTC)
    assert receipt["target_day"] == "2026-09-21"
    assert receipt["issued_at_utc"] == issued.isoformat()
    assert receipt["target_close_utc"] == target.isoformat()
    assert receipt["issue_to_target_seconds"] == (target - issued).total_seconds()
    with sqlite3.connect(database) as conn:
        conn.executemany(
            "INSERT INTO daily_price VALUES (?, ?)",
            [("2026-09-20", 21000), ("2026-09-21", 25000)],
        )
    early = score(database, ledger, now=target - timedelta(microseconds=1))
    assert early["by_horizon"]["2"]["resolved_examples"] == 0
    result = score(database, ledger, now=target)["by_horizon"]["2"]
    assert result["resolved_examples"] == 1
    assert result["hybrid_mae_usd"] == abs(25000 - receipt["hybrid_forecast_usd"])
    assert result["persistence_mae_usd"] == abs(25000 - receipt["origin_close_usd"])
    assert score(database, ledger, now=target)["by_horizon"]["2"] == result


def test_two_day_skips_origin_that_aged_during_training(tmp_path, monkeypatch):
    database = _database(tmp_path)
    ledger = tmp_path / "ledger.jsonl"
    start = datetime(2026, 9, 20, 23, 59, 59, tzinfo=UTC)
    monkeypatch.setattr(phase5, "_utc_now", lambda: start + timedelta(seconds=1))
    assert issue(database, ledger, now=start, horizons=(2,)) == []
    assert not ledger.exists()
