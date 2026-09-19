"""CEO mobile mission board must show only validated, real completed-run records."""

from __future__ import annotations

from typing import Any

import pytest
from scripts.render_ceo_mission_board import build_mission_board


def sample_report() -> dict[str, Any]:
    return {
        "status": "COMPLETED",
        "worker_type": "DETERMINISTIC_MARKET_DATA_PIPELINE_NOT_AI_AGENT",
        "persistence": "PRIVATE_GITHUB_DATA_BRANCH",
        "instrument": "market:coinbase:spot:btc-usd",
        "source": "source:coinbase.advanced-trade.public",
        "fetched_count": 3,
        "inserted_count": 0,
        "archive_total_count": 90,
        "started_at_utc": "2026-09-19T17:29:00+00:00",
        "completed_at_utc": "2026-09-19T17:29:01+00:00",
        "source_time_utc": "2026-09-19T17:29:01+00:00",
        "first_archived_bar_utc": "2026-06-21T00:00:00+00:00",
        "last_archived_bar_utc": "2026-09-18T00:00:00+00:00",
        "sqlite_sha256": "a" * 64,
        "run_id": "123456789-1",
    }


def test_board_shows_only_actual_worker_and_private_links() -> None:
    board = build_mission_board(sample_report(), run_id="123456789")
    assert "Total daily BTC/USD candles preserved | **90**" in board
    assert "New daily candles saved | **0**" in board
    assert "**NOT DEPLOYED**" in board
    assert "not a live dashboard" in board
    assert "actions/runs/123456789" in board
    assert "tree/data/btc-usd-daily/data" in board


def test_board_rejects_fictional_completed_agent() -> None:
    report = sample_report()
    report["worker_type"] = "AUTONOMOUS_AGENT"
    with pytest.raises(ValueError, match="Unexpected worker"):
        build_mission_board(report, run_id="123456789")


def test_board_rejects_mismatched_run_or_bad_counts() -> None:
    report = sample_report()
    with pytest.raises(ValueError, match="does not belong"):
        build_mission_board(report, run_id="987654321")
    report["inserted_count"] = 4
    with pytest.raises(ValueError, match="Inconsistent archive metrics"):
        build_mission_board(report, run_id="123456789")


def test_board_rejects_incomplete_run_or_invalid_hash() -> None:
    report = sample_report()
    report["status"] = "RUNNING"
    with pytest.raises(ValueError, match="actually completed"):
        build_mission_board(report, run_id="123456789")
    report["status"] = "COMPLETED"
    report["sqlite_sha256"] = "not-a-real-digest"
    with pytest.raises(ValueError, match="SHA-256"):
        build_mission_board(report, run_id="123456789")
