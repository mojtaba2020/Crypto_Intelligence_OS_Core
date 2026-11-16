"""Repository/branch labels are not GitHub visibility controls."""

from __future__ import annotations

from scripts.render_ceo_mission_board import build_mission_board
from scripts.render_ceo_private_console import render_console
from scripts.render_ceo_snapshot import render_snapshot


def _report(persistence: str) -> dict[str, str | int]:
    stamp = "2026-10-12T00:00:00+00:00"
    return {
        "status": "COMPLETED",
        "worker_type": "DETERMINISTIC_MARKET_DATA_PIPELINE_NOT_AI_AGENT",
        "persistence": persistence,
        "source": "source:coinbase.advanced-trade.public",
        "instrument": "market:coinbase:spot:btc-usd",
        "run_id": "456-1",
        "fetched_count": 2,
        "inserted_count": 1,
        "archive_total_count": 113,
        "first_archived_bar_utc": stamp,
        "last_archived_bar_utc": stamp,
        "started_at_utc": stamp,
        "completed_at_utc": stamp,
        "source_time_utc": stamp,
        "sqlite_sha256": "a" * 64,
    }


def test_mission_board_supports_new_and_legacy_storage_without_privacy_claim() -> None:
    for persistence in ("GITHUB_DATA_BRANCH", "PRIVATE_GITHUB_DATA_BRANCH"):
        board = build_mission_board(_report(persistence), run_id="456")
        assert "branch access follows repository visibility" in board
        assert "private GitHub branch" not in board


def test_snapshot_does_not_claim_a_private_branch() -> None:
    output = render_snapshot(_report("GITHUB_DATA_BRANCH"))
    assert "repository visibility applies" in output
    assert "Private GitHub branch" not in output


def test_offline_console_does_not_mislabel_github_access() -> None:
    facts: dict[str, str | int] = {
        "archive_total_count": 2,
        "sqlite_sha256": "a" * 64,
        "first_archived_bar_utc": "2026-09-10T00:00:00+00:00",
        "last_archived_bar_utc": "2026-09-11T00:00:00+00:00",
        "last_ingestion_completed_at_utc": "2026-09-12T00:00:00+00:00",
        "last_ingestion_run_id": "456-1",
    }
    output = render_console(facts, run_id="789")
    assert "verify visibility before sharing" in output
    assert "PRIVATE · CEO" not in output
    assert "persistent private BTC/USD archive" not in output
