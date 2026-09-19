#!/usr/bin/env python3
"""Create a factual, private GitHub-native CEO mission board for an actual BTC data run.

This report is a completed-run snapshot shown in GitHub Actions on mobile; it is
not a hosted dashboard or a live autonomous agent control surface.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

REPORT_PATH = Path("data/btc_ingestion_report.json")
REPOSITORY = "mojtaba2020/Crypto_Intelligence_OS_Core"
DATA_BRANCH_URL = f"https://github.com/{REPOSITORY}/tree/data/btc-usd-daily/data"
WORKFLOW_URL = f"https://github.com/{REPOSITORY}/actions/workflows/btc_daily_durable.yml"


def build_mission_board(report: dict[str, Any], *, run_id: str) -> str:
    """Validate real run data before rendering operational status in Markdown."""
    if report.get("status") != "COMPLETED":
        raise ValueError("Only an actually completed ingestion can be displayed as completed")
    if report.get("worker_type") != "DETERMINISTIC_MARKET_DATA_PIPELINE_NOT_AI_AGENT":
        raise ValueError("Unexpected worker type")
    if report.get("persistence") != "PRIVATE_GITHUB_DATA_BRANCH":
        raise ValueError("No verified persistent private data branch")
    if report.get("instrument") != "market:coinbase:spot:btc-usd":
        raise ValueError("Unexpected instrument")
    if report.get("source") != "source:coinbase.advanced-trade.public":
        raise ValueError("Unexpected source")

    numeric_keys = ("fetched_count", "inserted_count", "archive_total_count")
    for key in numeric_keys:
        value = report.get(key)
        if type(value) is not int or value < 0:
            raise ValueError(f"Invalid run metric: {key}")
    if (
        report["archive_total_count"] < 1
        or report["fetched_count"] < 1
        or report["inserted_count"] > report["fetched_count"]
        or report["inserted_count"] > report["archive_total_count"]
    ):
        raise ValueError("Inconsistent archive metrics")

    dates: dict[str, datetime] = {}
    date_keys = (
        "started_at_utc",
        "completed_at_utc",
        "source_time_utc",
        "first_archived_bar_utc",
        "last_archived_bar_utc",
    )
    for key in date_keys:
        value = report.get(key)
        if not isinstance(value, str):
            raise ValueError(f"Missing UTC timestamp: {key}")
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if timestamp.utcoffset() is None or timestamp.utcoffset().total_seconds() != 0:
            raise ValueError(f"Timestamp must be UTC: {key}")
        dates[key] = timestamp
    if (
        dates["started_at_utc"] > dates["completed_at_utc"]
        or dates["first_archived_bar_utc"] > dates["last_archived_bar_utc"]
        or dates["last_archived_bar_utc"] > dates["source_time_utc"]
    ):
        raise ValueError("Invalid task/data time order")

    digest = report.get("sqlite_sha256")
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise ValueError("Invalid SQLite SHA-256")
    if not run_id.isascii() or not run_id.isdecimal():
        raise ValueError("GitHub run ID must be numeric")
    recorded_run_id = report.get("run_id")
    if not isinstance(recorded_run_id, str) or not recorded_run_id.startswith(run_id + "-"):
        raise ValueError("Report does not belong to this workflow run")

    run_url = f"https://github.com/{REPOSITORY}/actions/runs/{run_id}"
    return (
        "# CEO Control Tower · BTC data mission\n\n"
        "> **Completed-run snapshot, not a live dashboard.** This report contains "
        "observed metrics from one real deterministic Python worker. No autonomous "
        "AI employee or live heartbeat is implied.\n\n"
        "## Mission status · ✅ COMPLETED\n\n"
        "| Verified metric | Value |\n"
        "|:--|--:|\n"
        f"| Total daily BTC/USD candles preserved | **{report['archive_total_count']}** |\n"
        f"| Candles validated during this run | **{report['fetched_count']}** |\n"
        f"| New daily candles saved | **{report['inserted_count']}** |\n\n"
        "## Real worker activity\n\n"
        "| Worker / planned role | State | Evidence |\n"
        "|:--|:--|:--|\n"
        f"| Public BTC/USD collector + quality validator (deterministic code) | "
        f"COMPLETED | [Run {run_id}]({run_url}) |\n"
        "| Autonomous Cycle Research Agent | **NOT DEPLOYED** | No execution record |\n"
        "| Autonomous Hybrid Intelligence Agent | **NOT DEPLOYED** | No execution record |\n\n"
        "## Provenance and data integrity\n\n"
        f"- First archived candle (UTC): `{dates['first_archived_bar_utc'].isoformat()}`\n"
        f"- Last archived candle (UTC): `{dates['last_archived_bar_utc'].isoformat()}`\n"
        f"- Collector started (UTC): `{dates['started_at_utc'].isoformat()}`\n"
        f"- Collector completed (UTC): `{dates['completed_at_utc'].isoformat()}`\n"
        f"- Coinbase server timestamp (UTC): `{dates['source_time_utc'].isoformat()}`\n"
        f"- SQLite SHA-256: `{digest}`\n"
        f"- [Open persistent data and ingestion report — private GitHub branch]"
        f"({DATA_BRANCH_URL})\n\n"
        "## CEO actions available now\n\n"
        f"- [Inspect this real run and its step-by-step logs]({run_url})\n"
        f"- [Start a new read-only collection mission via **Run workflow**]"
        f"({WORKFLOW_URL})\n"
        "- To cancel an active GitHub Actions run, use the GitHub Actions run page. "
        "This historical snapshot itself has no interactive or live controls.\n\n"
        "**Scope:** BTC/USD public market-data research only. No exchange accounts, "
        "API keys, orders, capital transfers, or autonomous trading.\n"
    )


def main() -> int:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    if not summary_path:
        raise ValueError("GITHUB_STEP_SUMMARY is required")
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    with Path(summary_path).open("a", encoding="utf-8") as output:
        output.write(build_mission_board(report, run_id=run_id))
    print(f"CEO mission board published for completed GitHub run {run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
