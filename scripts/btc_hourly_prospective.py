#!/usr/bin/env python3
"""Research-only hourly BTC-USD prospective forecasts; Coinbase Exchange candles."""
from __future__ import annotations

import argparse
import json
from itertools import pairwise
import math
import statistics
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

API = "https://api.exchange.coinbase.com/products/BTC-USD/candles"
HORIZONS = (1, 4, 12, 24)
VERSION = "hourly-ridge-free-momentum-v1"


def fetch(now: datetime, hours: int = 720) -> list[tuple[datetime, float]]:
    """Page Coinbase's 300-candle maximum; never use the currently open hour."""
    end = now.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
    values: dict[datetime, float] = {}
    cursor = end
    while cursor > end - timedelta(hours=hours):
        start = max(end - timedelta(hours=hours), cursor - timedelta(hours=299))
        params = urllib.parse.urlencode({
            "granularity": 3600,
            "start": start.isoformat().replace("+00:00", "Z"),
            "end": cursor.isoformat().replace("+00:00", "Z"),
        })
        request = urllib.request.Request(
            f"{API}?{params}", headers={"User-Agent": "Crypto-Intelligence-OS research"}
        )
        with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
            payload = json.load(response)
        if not isinstance(payload, list):
            raise ValueError("Coinbase candle response is not a list")
        for candle in payload:
            hour = datetime.fromtimestamp(int(candle[0]), UTC)
            close = float(candle[4])
            if start <= hour < end and math.isfinite(close) and close > 0:
                values[hour] = close
        cursor = start
    ordered = sorted(values.items())
    if len(ordered) < hours:
        raise ValueError("Hourly history incomplete")
    if any(b[0] - a[0] != timedelta(hours=1) for a, b in pairwise(ordered)):
        raise ValueError("Missing hourly candle")
    if ordered[-1][0] != end - timedelta(hours=1):
        raise ValueError("Latest completed hourly candle unavailable")
    return ordered


def ledger_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def run(now: datetime, ledger: Path, report: Path) -> dict:
    candles = fetch(now)
    origin, current = candles[-1]
    existing = ledger_rows(ledger)
    keys = {(r["version"], r["origin_hour_utc"], r["horizon_hours"]) for r in existing}
    new = []
    # Past-only hourly log returns, with a shrinkage-to-persistence momentum forecast.
    returns = [math.log(b[1] / a[1]) for a, b in pairwise(candles)]
    momentum = statistics.mean(returns[-24:])
    volatility = statistics.pstdev(returns[-168:])
    for horizon in HORIZONS:
        if (VERSION, origin.isoformat(), horizon) in keys:
            continue
        forecast = current * math.exp(max(-0.2, min(0.2, momentum * horizon * 0.25)))
        new.append({
            "version": VERSION, "issued_at_utc": now.astimezone(UTC).isoformat(),
            "origin_hour_utc": origin.isoformat(),
            "target_hour_utc": (origin + timedelta(hours=horizon)).isoformat(),
            "horizon_hours": horizon, "origin_close_usd": current,
            "forecast_usd": forecast, "persistence_usd": current,
            "observed_volatility_hourly": volatility, "training_hours": len(candles),
            "source": "coinbase:exchange:BTC-USD:1h:close",
            "research_only": True,
        })
    if new:
        ledger.parent.mkdir(parents=True, exist_ok=True)
        with ledger.open("a", encoding="utf-8") as output:
            for row in new:
                output.write(json.dumps(row, sort_keys=True) + "\n")
    prices = {hour.isoformat(): price for hour, price in candles}
    scores = {}
    for horizon in HORIZONS:
        resolved = [
            (abs(row["forecast_usd"] - prices[row["target_hour_utc"]]),
             abs(row["persistence_usd"] - prices[row["target_hour_utc"]]))
            for row in ledger_rows(ledger)
            if row["version"] == VERSION and row["horizon_hours"] == horizon
            and row["target_hour_utc"] in prices
            and datetime.fromisoformat(row["issued_at_utc"])
            < datetime.fromisoformat(row["target_hour_utc"])
        ]
        scores[str(horizon)] = {
            "resolved": len(resolved),
            "model_mae_usd": statistics.mean(x for x, _ in resolved) if resolved else None,
            "persistence_mae_usd": statistics.mean(y for _, y in resolved) if resolved else None,
        }
    result = {"status": "HOURLY_PROSPECTIVE", "origin_hour_utc": origin.isoformat(),
              "issued": new, "scores": scores, "research_only": True}
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(datetime.now(UTC), args.ledger, args.report), indent=2))


if __name__ == "__main__":
    main()
