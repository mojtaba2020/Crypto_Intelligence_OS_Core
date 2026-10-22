#!/usr/bin/env python3
"""Point-in-time hourly momentum diagnostic; NOT trained AI or holdout validation."""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

API = "https://api.exchange.coinbase.com"
HORIZONS = (1, 2, 3, 4, 12)
HEADERS = {"User-Agent": "Crypto-Intelligence-OS/1.0", "Accept": "application/json"}


def fetch_closes() -> list[float]:
    now = datetime.now(UTC)
    end = int(now.timestamp()) // 3600 * 3600
    start = end - 200 * 3600
    query = urllib.parse.urlencode(
        {
            "start": datetime.fromtimestamp(start, UTC).isoformat(),
            "end": datetime.fromtimestamp(end, UTC).isoformat(),
            "granularity": 3600,
        }
    )
    request = urllib.request.Request(  # noqa: S310
        API + "/products/BTC-USD/candles?" + query, headers=HEADERS
    )
    with urllib.request.urlopen(request, timeout=25) as response:  # noqa: S310
        rows = json.load(response)
    return [float(row[4]) for row in sorted(rows) if int(row[0]) < end]


def evaluate(closes: list[float]) -> dict:
    """Chronological oldest-to-newest closes; use only past closes at each origin."""
    if len(closes) < 180 or any(p <= 0 for p in closes):
        raise ValueError("Need at least 180 positive hourly closes")
    results = []
    for horizon in HORIZONS:
        model_errors = []
        baseline_errors = []
        for origin in range(23, len(closes) - horizon):
            current = closes[origin]
            actual = closes[origin + horizon]
            change = current - closes[origin - 23]
            candidate = max(0.01, current + 0.25 * horizon * change / 24)
            model_errors.append(abs(candidate - actual) / actual)
            baseline_errors.append(abs(current - actual) / actual)
        model_mape = 100 * sum(model_errors) / len(model_errors)
        baseline_mape = 100 * sum(baseline_errors) / len(baseline_errors)
        results.append(
            {
                "horizon_hours": horizon,
                "samples": len(model_errors),
                "momentum_mape_pct": round(model_mape, 5),
                "persistence_mape_pct": round(baseline_mape, 5),
                "momentum_better": model_mape < baseline_mape,
            }
        )
    return {
        "status": "SHORT_OVERLAPPING_HOURLY_DIAGNOSTIC_NOT_AI_NOT_HOLDOUT",
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    closes = json.loads(args.input.read_text(encoding="utf-8")) if args.input else fetch_closes()
    report = evaluate(closes)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
