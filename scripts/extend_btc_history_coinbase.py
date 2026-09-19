#!/usr/bin/env python3
"""Extend the research price archive with official Coinbase BTC-USD daily closes.

Coin Metrics remains the historical source through its last available day.
Coinbase is used only for later completed UTC days. A short overlap is fetched
for a source-transition sanity check; overlapping Coin Metrics rows are never
overwritten.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import urllib.parse
import urllib.request
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

API_URL = "https://api.exchange.coinbase.com/products/BTC-USD/candles"
SOURCE = "coinbase:exchange:BTC-USD:1d:close"


def _fetch(start: date, end: date) -> dict[date, str]:
    params = urllib.parse.urlencode(
        {
            "granularity": 86400,
            "start": f"{start.isoformat()}T00:00:00Z",
            "end": f"{(end + timedelta(days=1)).isoformat()}T00:00:00Z",
        }
    )
    request = urllib.request.Request(  # noqa: S310 -- fixed HTTPS Coinbase URL
        f"{API_URL}?{params}",
        headers={"User-Agent": "Crypto-Intelligence-OS/0.3 research"},
    )
    with urllib.request.urlopen(  # noqa: S310 -- fixed HTTPS request above
        request,
        timeout=60,
    ) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Unexpected Coinbase response")

    prices: dict[date, str] = {}
    for candle in payload:
        if not isinstance(candle, list) or len(candle) < 6:
            raise ValueError("Malformed Coinbase candle")
        day = datetime.fromtimestamp(int(candle[0]), UTC).date()
        if start <= day <= end:
            close = str(candle[4])
            if float(close) <= 0:
                raise ValueError(f"Invalid Coinbase close on {day}")
            prices[day] = close

    expected = {
        start + timedelta(days=index)
        for index in range((end - start).days + 1)
    }
    missing = sorted(expected - set(prices))
    if missing:
        raise ValueError(f"Coinbase daily candles missing: {missing[:5]}")
    return prices


def extend(
    database: Path,
    *,
    completed_through: date,
    overlap_days: int = 4,
) -> dict[str, object]:
    if overlap_days < 1:
        raise ValueError("overlap_days must be positive")

    with sqlite3.connect(database) as connection:
        last_row = connection.execute(
            "SELECT day, price_usd FROM daily_price ORDER BY day DESC LIMIT 1"
        ).fetchone()
        if not last_row:
            raise ValueError("Historical archive is empty")

        historical_last = date.fromisoformat(last_row[0])
        if completed_through <= historical_last:
            raise ValueError("No Coinbase extension days requested")

        fetch_start = historical_last - timedelta(days=overlap_days - 1)
        prices = _fetch(fetch_start, completed_through)

        overlap_rows = connection.execute(
            "SELECT day, price_usd FROM daily_price WHERE day >= ? ORDER BY day",
            (fetch_start.isoformat(),),
        ).fetchall()
        overlap_diffs: list[tuple[date, float]] = []
        for raw_day, raw_price in overlap_rows:
            day = date.fromisoformat(raw_day)
            if day in prices:
                reference = float(raw_price)
                difference = 100 * abs(float(prices[day]) - reference) / reference
                overlap_diffs.append((day, difference))

        if not overlap_diffs:
            raise ValueError("No source-overlap dates available for transition check")

        max_overlap = max(value for _, value in overlap_diffs)
        if max_overlap > 5.0:
            raise ValueError(
                "Coinbase/Coin Metrics overlap divergence too large: "
                f"{max_overlap:.3f}%"
            )

        extension_start = historical_last + timedelta(days=1)
        extension_days = [
            extension_start + timedelta(days=index)
            for index in range((completed_through - extension_start).days + 1)
        ]

        with connection:
            connection.executemany(
                "INSERT INTO daily_price(day, price_usd, source) VALUES (?, ?, ?)",
                (
                    (day.isoformat(), prices[day], SOURCE)
                    for day in extension_days
                ),
            )
            provenance = {
                "extension_source_url": API_URL,
                "extension_source": SOURCE,
                "source_transition_day": extension_start.isoformat(),
                "coinbase_completed_through": completed_through.isoformat(),
                "coinbase_overlap_max_pct": f"{max_overlap:.8f}",
                "coinbase_downloaded_at_utc": datetime.now(UTC).isoformat(),
            }
            connection.executemany(
                "INSERT OR REPLACE INTO provenance(key, value) VALUES (?, ?)",
                provenance.items(),
            )

        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        if not integrity or integrity[0] != "ok":
            raise ValueError("Extended SQLite integrity check failed")
        total = connection.execute("SELECT COUNT(*) FROM daily_price").fetchone()[0]

    return {
        "status": "EXTENDED_WITH_COINBASE",
        "historical_source": "coinmetrics:btc:PriceUSD:1d",
        "historical_last_day": historical_last.isoformat(),
        "extension_source": SOURCE,
        "extension_first_day": extension_start.isoformat(),
        "completed_through": completed_through.isoformat(),
        "inserted_days": len(extension_days),
        "overlap_days_checked": len(overlap_diffs),
        "overlap_max_pct": max_overlap,
        "rows_total": total,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--completed-through",
        type=date.fromisoformat,
        default=datetime.now(UTC).date() - timedelta(days=1),
    )
    arguments = parser.parse_args()
    report = extend(
        arguments.database,
        completed_through=arguments.completed_through,
    )
    arguments.report.parent.mkdir(parents=True, exist_ok=True)
    arguments.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
