"""Prospective forecasts cannot be issued on unfinished or stale data."""

import json
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
    assert report["ledger_entries"] == 9
    assert set(report["by_horizon"]) == {"1", "3", "7", "14", "21", "30", "90", "180", "365"}
    assert all(row["resolved_examples"] == 0 for row in report["by_horizon"].values())


def test_issue_rejects_unfinished_day_and_stale_archive(tmp_path):
    database = _database(tmp_path)
    ledger = tmp_path / "ledger.jsonl"
    with pytest.raises(ValueError, match="completed"):
        issue(database, ledger, now=datetime(2026, 9, 19, 12, tzinfo=UTC))
    with pytest.raises(ValueError, match="stale"):
        issue(database, ledger, now=datetime(2026, 9, 23, 12, tzinfo=UTC))


def test_forecast_issued_on_target_day_before_daily_close_is_scored(tmp_path):
    database = _database(tmp_path)
    ledger = tmp_path / "ledger.jsonl"
    issue(database, ledger, now=datetime(2026, 9, 20, 8, 17, tzinfo=UTC))
    # Only synthetic next day's outcome is inserted *after* the forecast is issued.
    with sqlite3.connect(database) as connection:
        connection.execute("INSERT INTO daily_price VALUES (?, ?)", ("2026-09-20", 24000.0))
    report = score(database, ledger, now=datetime(2026, 9, 21, 0, 1, tzinfo=UTC))
    assert report["by_horizon"]["1"]["resolved_examples"] == 1
    assert report["by_horizon"]["3"]["resolved_examples"] == 0


def test_forecast_issued_at_target_close_does_not_count_as_prospective(tmp_path):
    database = _database(tmp_path)
    ledger = tmp_path / "ledger.jsonl"
    issue(database, ledger, now=datetime(2026, 9, 20, 8, 17, tzinfo=UTC))
    rows = [json.loads(line) for line in ledger.read_text().splitlines()]
    for row in rows:
        if row["horizon_days"] == 1:
            row["issued_at_utc"] = "2026-09-21T00:00:00+00:00"
    ledger.write_text("".join(json.dumps(row) + "\n" for row in rows))
    with sqlite3.connect(database) as connection:
        connection.execute("INSERT INTO daily_price VALUES (?, ?)", ("2026-09-20", 24000.0))
    report = score(database, ledger, now=datetime(2026, 9, 21, 0, 1, tzinfo=UTC))
    assert report["by_horizon"]["1"]["resolved_examples"] == 0
