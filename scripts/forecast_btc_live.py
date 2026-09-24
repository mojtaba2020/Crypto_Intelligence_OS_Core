#!/usr/bin/env python3
"""Generate timestamped BTC/USD numerical forecasts from live Coinbase public market data.

Research prototype: daily models are selected by an explicit historical tournament
report. Hourly models are exploratory and NOT historically validated. No trades.
"""
from __future__ import annotations

import argparse
import json
import math
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

DAILY_HORIZONS = (1, 2, 3, 7, 14, 21, 30, 90, 180, 365)
HOURLY_HORIZONS = (1, 2, 3, 4, 12)
API = "https://api.exchange.coinbase.com"
HEADERS = {"User-Agent": "Crypto-Intelligence-OS/1.0", "Accept": "application/json"}


def fetch_json(path: str) -> object:
    if not path.startswith(("/products/BTC-USD/ticker", "/products/BTC-USD/candles?")):
        raise ValueError("Unsupported API endpoint")
    request = urllib.request.Request(API + path, headers=HEADERS)  # noqa: S310
    with urllib.request.urlopen(request, timeout=25) as response:  # noqa: S310
        return json.load(response)


def candles(granularity: int, now: datetime) -> dict[int, float]:
    # Coinbase returns at most 300 candles. Request 200 closed intervals.
    end = int(now.timestamp()) // granularity * granularity
    start = end - 200 * granularity
    query = urllib.parse.urlencode({
        "start": datetime.fromtimestamp(start, UTC).isoformat(),
        "end": datetime.fromtimestamp(end, UTC).isoformat(),
        "granularity": granularity,
    })
    raw = fetch_json("/products/BTC-USD/candles?" + query)
    if not isinstance(raw, list):
        raise ValueError("Unexpected candle API response")
    values = {}
    for row in raw:
        if not isinstance(row, list) or len(row) < 5:
            raise ValueError("Malformed candle")
        timestamp, close = int(row[0]), float(row[4])
        if timestamp < end and math.isfinite(close) and close > 0:
            values[timestamp] = close
    for offset in range(1, 92 if granularity == 86400 else 25):
        if end - offset * granularity not in values:
            raise ValueError("Missing required closed candle")
    return values


def forecast(model: str, current: float, prices: dict[int, float],
             origin: int, horizon: int, unit: int) -> float:
    if model == "persistence":
        return current
    if model not in ("momentum_30d_quarter", "momentum_90d_quarter"):
        raise ValueError("Unknown model: " + model)
    if unit != 86400:
        raise ValueError("Daily momentum model cannot be used for hourly predictions")
    lookback = 30 if model == "momentum_30d_quarter" else 90
    previous = prices[origin - lookback * unit]
    origin_close = prices[origin]
    return max(0.01, current + 0.25 * horizon * (origin_close - previous) / lookback)


def run(selection_report: Path, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("Time must be timezone-aware")
    now = now.astimezone(UTC)
    selection = json.loads(selection_report.read_text(encoding="utf-8"))
    if selection.get("status") != "MODEL_TOURNAMENT_RESEARCH_ONLY":
        raise ValueError("Expected a historical model tournament report")
    by_horizon = {r["horizon_days"]: r for r in selection["results"]}
    if set(by_horizon) != set(DAILY_HORIZONS):
        raise ValueError("Selection report must cover all ten daily horizons")
    ticker = fetch_json("/products/BTC-USD/ticker")
    if not isinstance(ticker, dict):
        raise ValueError("Unexpected ticker API response")
    spot = float(ticker["price"])
    ticker_time = datetime.fromisoformat(ticker["time"].replace("Z", "+00:00"))
    if not math.isfinite(spot) or spot <= 0 or abs((now - ticker_time).total_seconds()) > 300:
        raise ValueError("Invalid or stale live BTC price")
    daily = candles(86400, now)
    hourly = candles(3600, now)
    daily_origin = int(now.timestamp()) // 86400 * 86400 - 86400
    hourly_origin = int(now.timestamp()) // 3600 * 3600 - 3600
    forecasts = []
    for horizon in HOURLY_HORIZONS:
        # Explicit provisional baseline: never describe as an AI-trained hourly model.
        value = forecast("persistence", spot, hourly, hourly_origin, horizon, 3600)
        forecasts.append({
            "timeframe": f"{horizon}h", "horizon_hours": horizon,
            "target_utc": (now + timedelta(hours=horizon)).isoformat(),
            "predicted_price_usd": round(value, 2),
            "change_pct": round(100 * (value / spot - 1), 4),
            "model": "persistence",
            "evidence": "UNVALIDATED_HOURLY_BASELINE",
        })
    for horizon in DAILY_HORIZONS:
        result = by_horizon[horizon]
        model = result["selected_on_validation"]
        value = forecast(model, spot, daily, daily_origin, horizon, 86400)
        forecasts.append({
            "timeframe": f"{horizon}d", "horizon_days": horizon,
            "target_utc": (now + timedelta(days=horizon)).isoformat(),
            "predicted_price_usd": round(value, 2),
            "change_pct": round(100 * (value / spot - 1), 4),
            "model": model,
            "evidence": "HISTORICAL_SELECTION_NOT_PROSPECTIVE_VALIDATION",
            "locked_test_examples": result["locked_test_examples"],
            "locked_test_improvement_vs_persistence_pct":
                result["selected_test_improvement_vs_persistence_pct"],
        })
    return {
        "status": "LIVE_NUMERIC_RESEARCH_FORECAST_NOT_TRADING_ADVICE",
        "generated_at_utc": now.isoformat(), "ticker_at_utc": ticker_time.isoformat(),
        "market": "BTC-USD", "source": "Coinbase Exchange public API",
        "spot_price_usd": round(spot, 2), "forecasts": forecasts,
        "warning": (
            "Hourly values are unvalidated persistence baselines; daily historical "
            "selection does not establish future accuracy."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.selection_report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
