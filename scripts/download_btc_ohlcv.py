#!/usr/bin/env python3
"""Download audited Coinbase BTC-USD daily OHLCV, separate from composite prices."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from extend_btc_history_coinbase import API_URL, _fetch


def download(database: Path, *, start: date, end: date) -> dict[str, object]:
    if start > end or end >= datetime.now(UTC).date():
        raise ValueError("Request only completed UTC days in chronological order")
    database.parent.mkdir(parents=True, exist_ok=True)
    rows: list[tuple[str, float, float, float, float, float]] = []
    current = start
    while current <= end:
        chunk_end = min(end, current + timedelta(days=199))
        candles = _fetch(current, chunk_end, full_candles=True)
        for day in sorted(candles):
            low, high, opening, closing, volume = candles[day]
            if not (0 < low <= min(opening, closing) <= max(opening, closing) <= high):
                raise ValueError(f"Invalid OHLC on {day}")
            if volume < 0:
                raise ValueError(f"Invalid volume on {day}")
            rows.append((day.isoformat(), opening, high, low, closing, volume))
        current = chunk_end + timedelta(days=1)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS coinbase_ohlcv ("
            "day TEXT PRIMARY KEY, open REAL NOT NULL, high REAL NOT NULL, "
            "low REAL NOT NULL, close REAL NOT NULL, volume_btc REAL NOT NULL)"
        )
        with connection:
            connection.executemany(
                "INSERT OR REPLACE INTO coinbase_ohlcv VALUES (?, ?, ?, ?, ?, ?)", rows
            )
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("OHLCV archive integrity check failed")
    return {
        "status": "COINBASE_OHLCV_DOWNLOADED",
        "source": API_URL,
        "first_day": start.isoformat(),
        "last_day": end.isoformat(),
        "daily_candles": len(rows),
        "note": "Separate exchange OHLCV archive; not spliced into Coin Metrics history.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--start", type=date.fromisoformat, default=date(2025, 1, 1))
    parser.add_argument(
        "--end",
        type=date.fromisoformat,
        default=datetime.now(UTC).date() - timedelta(days=1),
    )
    args = parser.parse_args()
    report = download(args.database, start=args.start, end=args.end)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
