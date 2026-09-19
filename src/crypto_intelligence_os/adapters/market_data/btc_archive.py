"""SQLite archive for validated, immutable-first-observation BTC/USD daily bars.

The database is a private research artifact, not a live exchange or trading database.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from crypto_intelligence_os.market_data import BarStatus, OHLCVBar, Timeframe

EXPECTED_INSTRUMENT = "market:coinbase:spot:btc-usd"
EXPECTED_SOURCE = "source:coinbase.advanced-trade.public"


class BTCArchive:
    """Idempotent historical archive preserving the original system ingestion time."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path)
        self._connection.execute("PRAGMA busy_timeout = 30000")
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS candles (
                open_time TEXT PRIMARY KEY NOT NULL,
                record TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS ingestion_runs (
                run_id TEXT PRIMARY KEY NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                source_time TEXT NOT NULL,
                requested_start TEXT NOT NULL,
                requested_end TEXT NOT NULL,
                fetched_count INTEGER NOT NULL,
                inserted_count INTEGER NOT NULL,
                total_count INTEGER NOT NULL
            );
            """
        )

    def __enter__(self) -> BTCArchive:
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        self._connection.close()

    def last_open_time(self) -> datetime | None:
        row = self._connection.execute("SELECT MAX(open_time) FROM candles").fetchone()
        return datetime.fromisoformat(row[0]) if row and row[0] else None

    def count(self) -> int:
        row = self._connection.execute("SELECT COUNT(*) FROM candles").fetchone()
        return int(row[0])

    def all_bars(self) -> tuple[OHLCVBar, ...]:
        rows = self._connection.execute(
            "SELECT record FROM candles ORDER BY open_time"
        ).fetchall()
        return tuple(OHLCVBar.model_validate_json(row[0]) for row in rows)

    def integrity_check(self) -> None:
        row = self._connection.execute("PRAGMA integrity_check").fetchone()
        if not row or row[0] != "ok":
            raise ValueError(f"SQLite integrity_check failed: {row}")

    def persist(
        self,
        bars: tuple[OHLCVBar, ...],
        *,
        run_id: str,
        started_at: datetime,
        completed_at: datetime,
        source_time: datetime,
        requested_start: datetime,
        requested_end: datetime,
    ) -> int:
        """Insert only new final bars; reject silent exchange-history revisions."""
        inserted = 0
        with self._connection:
            for bar in bars:
                if (
                    bar.instrument_id != EXPECTED_INSTRUMENT
                    or bar.source_id != EXPECTED_SOURCE
                    or bar.timeframe is not Timeframe.ONE_DAY
                    or bar.status is not BarStatus.FINAL
                    or bar.available_at > source_time
                    or bar.ingested_at > completed_at
                ):
                    raise ValueError(f"Invalid candle for durable archive: {bar.open_time}")
                key = bar.open_time.isoformat()
                existing = self._connection.execute(
                    "SELECT record FROM candles WHERE open_time = ?", (key,)
                ).fetchone()
                if existing:
                    old = OHLCVBar.model_validate_json(existing[0])
                    if old.model_dump(exclude={"ingested_at"}) != bar.model_dump(
                        exclude={"ingested_at"}
                    ):
                        raise ValueError(
                            f"Historical candle revision at {key}; manual review required"
                        )
                    continue
                self._connection.execute(
                    "INSERT INTO candles(open_time, record) VALUES (?, ?)",
                    (key, bar.model_dump_json()),
                )
                inserted += 1
            self._connection.execute(
                """
                INSERT INTO ingestion_runs(
                    run_id, started_at, completed_at, source_time,
                    requested_start, requested_end, fetched_count, inserted_count, total_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    started_at.isoformat(),
                    completed_at.isoformat(),
                    source_time.isoformat(),
                    requested_start.isoformat(),
                    requested_end.isoformat(),
                    len(bars),
                    inserted,
                    self.count(),
                ),
            )
        self.integrity_check()
        return inserted
