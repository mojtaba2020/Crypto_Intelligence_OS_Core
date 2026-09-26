"""Provider-neutral immutable OHLCV archive for long-history research."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from crypto_intelligence_os.market_data import BarStatus, OHLCVBar


class HistoricalOHLCVArchive:
    """Store first-observed final bars without silently accepting provider revisions."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path)
        self._connection.execute("PRAGMA busy_timeout = 30000")
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS bars (
                source_id TEXT NOT NULL,
                instrument_id TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                open_time TEXT NOT NULL,
                record TEXT NOT NULL,
                PRIMARY KEY(source_id, instrument_id, timeframe, open_time)
            );
            CREATE INDEX IF NOT EXISTS bars_lookup
            ON bars(instrument_id, timeframe, open_time);
            """
        )

    def __enter__(self) -> HistoricalOHLCVArchive:
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        self._connection.close()

    def integrity_check(self) -> None:
        row = self._connection.execute("PRAGMA integrity_check").fetchone()
        if not row or row[0] != "ok":
            raise ValueError(f"SQLite integrity_check failed: {row}")

    def persist(self, bars: tuple[OHLCVBar, ...]) -> int:
        """Insert new FINAL bars and reject any silent historical rewrite."""
        inserted = 0
        with self._connection:
            for bar in bars:
                if bar.status is not BarStatus.FINAL:
                    raise ValueError("Historical archive accepts FINAL bars only")
                key = (
                    bar.source_id,
                    bar.instrument_id,
                    bar.timeframe.value,
                    bar.open_time.isoformat(),
                )
                existing = self._connection.execute(
                    """
                    SELECT record FROM bars
                    WHERE source_id = ? AND instrument_id = ?
                      AND timeframe = ? AND open_time = ?
                    """,
                    key,
                ).fetchone()
                if existing:
                    old = OHLCVBar.model_validate_json(existing[0])
                    ignored = {"bar_id", "ingested_at", "quality"}
                    if old.model_dump(exclude=ignored) != bar.model_dump(exclude=ignored):
                        raise ValueError(
                            "Historical provider revision requires explicit review: "
                            f"{bar.source_id} {bar.open_time.isoformat()}"
                        )
                    continue
                self._connection.execute(
                    """
                    INSERT INTO bars(source_id, instrument_id, timeframe, open_time, record)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (*key, bar.model_dump_json()),
                )
                inserted += 1
        self.integrity_check()
        return inserted

    def read(
        self,
        *,
        instrument_id: str,
        timeframe: str,
        source_id: str | None = None,
    ) -> tuple[OHLCVBar, ...]:
        if source_id is None:
            rows = self._connection.execute(
                """
                SELECT record FROM bars
                WHERE instrument_id = ? AND timeframe = ?
                ORDER BY open_time
                """,
                (instrument_id, timeframe),
            ).fetchall()
        else:
            rows = self._connection.execute(
                """
                SELECT record FROM bars
                WHERE instrument_id = ? AND timeframe = ? AND source_id = ?
                ORDER BY open_time
                """,
                (instrument_id, timeframe, source_id),
            ).fetchall()
        return tuple(OHLCVBar.model_validate_json(row[0]) for row in rows)

    def count(self) -> int:
        row = self._connection.execute("SELECT COUNT(*) FROM bars").fetchone()
        return int(row[0])


def validate_hourly_continuity(bars: tuple[OHLCVBar, ...]) -> None:
    """Reject duplicates, mixed streams, disorder, and missing hourly intervals."""
    if not bars:
        raise ValueError("No bars supplied")
    identity = {(bar.source_id, bar.instrument_id, bar.timeframe.value) for bar in bars}
    if len(identity) != 1:
        raise ValueError("Continuity validation requires one source/instrument/timeframe stream")
    previous = None
    seen = set()
    for bar in bars:
        if bar.open_time in seen:
            raise ValueError(f"Duplicate open_time: {bar.open_time.isoformat()}")
        if previous is not None:
            seconds = int((bar.open_time - previous).total_seconds())
            if seconds != 3600:
                raise ValueError(
                    f"Hourly continuity gap: {previous.isoformat()} -> {bar.open_time.isoformat()}"
                )
        seen.add(bar.open_time)
        previous = bar.open_time
