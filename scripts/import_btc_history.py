#!/usr/bin/env python3
"""Import Coin Metrics BTC PriceUSD daily research series, separately from Coinbase OHLCV.

Source: https://github.com/coinmetrics/data/blob/master/csv/btc.csv
License: CC BY-NC 4.0; personal noncommercial research only. PriceUSD is an
aggregated USD metric, NOT a Coinbase close or a historical OHLCV candle.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sqlite3
import urllib.request
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

SOURCE_URL = "https://raw.githubusercontent.com/coinmetrics/data/master/csv/btc.csv"
START = date(2011, 1, 1)


def import_history(csv_text: str, destination: Path, *, cutoff: date) -> dict[str, object]:
    reader = csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames or not {"time", "PriceUSD"}.issubset(reader.fieldnames):
        raise ValueError("Source CSV must include time and PriceUSD columns")
    prices: dict[date, str] = {}
    for row in reader:
        raw_day = (row.get("time") or "").strip()
        raw_price = (row.get("PriceUSD") or "").strip()
        if not raw_day or not raw_price:
            continue
        day = date.fromisoformat(raw_day[:10])
        if day < START or day > cutoff:
            continue
        try:
            price = Decimal(raw_price)
        except InvalidOperation as error:
            raise ValueError(f"Invalid price on {day}") from error
        if not price.is_finite() or price <= 0:
            raise ValueError(f"Invalid nonpositive price on {day}")
        if day in prices and prices[day] != raw_price:
            raise ValueError(f"Conflicting prices on {day}")
        prices[day] = raw_price
    if not prices:
        raise ValueError("No usable historical prices in requested date range")
    ordered = sorted(prices)
    missing = [
        (ordered[index - 1] + timedelta(days=1), ordered[index] - timedelta(days=1))
        for index in range(1, len(ordered))
        if (ordered[index] - ordered[index - 1]).days > 1
    ]
    if ordered[0] > START:
        missing.insert(0, (START, ordered[0] - timedelta(days=1)))
    if ordered[-1] < cutoff:
        missing.append((ordered[-1] + timedelta(days=1), cutoff))
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(destination) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS daily_price ("
            "day TEXT PRIMARY KEY, price_usd TEXT NOT NULL, source TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS provenance (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        connection.execute("DELETE FROM daily_price")
        connection.executemany(
            "INSERT INTO daily_price(day, price_usd, source) VALUES (?, ?, ?)",
            ((day.isoformat(), prices[day], "coinmetrics:btc:PriceUSD:1d") for day in ordered),
        )
        for key, value in {
            "source_url": SOURCE_URL,
            "license": "CC BY-NC 4.0; noncommercial research",
            "metric": "BTC PriceUSD daily aggregate; not Coinbase OHLCV",
            "source_csv_sha256": hashlib.sha256(csv_text.encode()).hexdigest(),
            "downloaded_at_utc": datetime.now(UTC).isoformat(),
        }.items():
            connection.execute(
                "INSERT OR REPLACE INTO provenance(key, value) VALUES (?, ?)", (key, value)
            )
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        if not integrity or integrity[0] != "ok":
            raise ValueError("Historical SQLite integrity check failed")
    return {
        "status": "IMPORTED",
        "source": SOURCE_URL,
        "license": "CC BY-NC 4.0; noncommercial research",
        "metric": "BTC PriceUSD 1d; NOT Coinbase OHLCV",
        "first_day": ordered[0].isoformat(),
        "last_day": ordered[-1].isoformat(),
        "requested_start": START.isoformat(),
        "requested_end": cutoff.isoformat(),
        "rows": len(ordered),
        "missing_ranges": [
            {"start": first.isoformat(), "end": last.isoformat()} for first, last in missing
        ],
        "source_csv_sha256": hashlib.sha256(csv_text.encode()).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, help="Optional downloaded source CSV")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--end", type=date.fromisoformat, default=datetime.now(UTC).date())
    arguments = parser.parse_args()
    if arguments.end < START:
        parser.error("End date must not precede 2011-01-01")
    if arguments.csv:
        csv_text = arguments.csv.read_text(encoding="utf-8-sig")
    else:
        with urllib.request.urlopen(SOURCE_URL, timeout=60) as response:
            csv_text = response.read().decode("utf-8-sig")
    report = import_history(csv_text, arguments.database, cutoff=arguments.end)
    arguments.report.parent.mkdir(parents=True, exist_ok=True)
    arguments.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
