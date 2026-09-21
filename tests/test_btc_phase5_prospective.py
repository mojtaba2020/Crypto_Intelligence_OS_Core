"""Prospective forecasts cannot be issued on unfinished or stale data."""

import sqlite3
from datetime import UTC, date, datetime, timedelta

import pytest
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


def test_issue_is_idempotent_and_targets_are_future(tmp_path):
    database = _database(tmp_path)
    ledger = tmp_path / "ledger.jsonl"
    now = datetime(2026, 9, 20, 12, tzinfo=UTC)
    created = issue(database, ledger, now=now)
    assert len(created) == 9
    assert all(date.fromisoformat(row["target_day"]) >= now.date() for row in created)
    assert issue(database, ledger, now=now) == []
    report = score(database, ledger, now=now)
    assert report["ledger_entries"] == 7
    assert set(report["by_horizon"]) == {"1", "3", "7", "14", "21", "30", "90", "180", "365"}
    assert all(row["resolved_examples"] == 0 for row in report["by_horizon"].values())


def test_issue_rejects_unfinished_day_and_stale_archive(tmp_path):
    database = _database(tmp_path)
    ledger = tmp_path / "ledger.jsonl"
    with pytest.raises(ValueError, match="completed"):
        issue(database, ledger, now=datetime(2026, 9, 19, 12, tzinfo=UTC))
    with pytest.raises(ValueError, match="stale"):
        issue(database, ledger, now=datetime(2026, 9, 23, 12, tzinfo=UTC))
