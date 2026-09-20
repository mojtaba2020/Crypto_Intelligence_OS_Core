#!/usr/bin/env python3
"""Research-only hourly BTC-USD prospective forecasts; Coinbase Exchange closed candles."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path

from crypto_intelligence_os.hybrid_forecasting import _estimate, _fit

API = "https://api.exchange.coinbase.com/products/BTC-USD/candles"
HORIZONS = (1, 4, 12, 24)
VERSION = "hourly-hybrid-ridge-v2"
FEATURE_WINDOWS = (1, 4, 12, 24, 72, 168)


def fetch(now: datetime, hours: int = 720) -> list[tuple[datetime, float]]:
    """Page Coinbase's 300-candle maximum; never use the currently open hour."""
    end = now.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
    values: dict[datetime, float] = {}
    cursor = end
    while cursor > end - timedelta(hours=hours):
        start = max(end - timedelta(hours=hours), cursor - timedelta(hours=299))
        params = urllib.parse.urlencode(
            {
                "granularity": 3600,
                "start": start.isoformat().replace("+00:00", "Z"),
                "end": cursor.isoformat().replace("+00:00", "Z"),
            }
        )
        request = urllib.request.Request(  # noqa: S310
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


def feature_vector(candles: list[tuple[datetime, float]], index: int) -> tuple[float, ...]:
    """Past-only log returns and realized volatility at the forecast origin."""
    current = candles[index][1]
    values = [math.log(current / candles[index - window][1]) for window in FEATURE_WINDOWS]
    returns = [math.log(candles[j][1] / candles[j - 1][1]) for j in range(index - 23, index + 1)]
    values.append(statistics.pstdev(returns))
    return tuple(values)


def train(candles: list[tuple[datetime, float]], horizon: int) -> tuple[float, float, int]:
    """Fit ridge on resolved labels; choose persistence blend on embargoed holdout."""
    last = len(candles) - 1
    examples = [
        (feature_vector(candles, index), math.log(candles[index + horizon][1] / candles[index][1]))
        for index in range(168, last - horizon + 1)
    ]
    if len(examples) < 240:
        raise ValueError("Insufficient resolved hourly training examples")
    calibration = 96
    split = len(examples) - calibration
    provisional = _fit(examples[: split - horizon], ridge=100.0)
    holdout = examples[split:]
    blend = min(
        (
            sum(
                abs(weight * _estimate(*provisional, features) - target)
                for features, target in holdout
            ),
            weight,
        )
        for weight in (0.0, 0.25, 0.5, 0.75, 1.0)
    )[1]
    fitted = _fit(examples, ridge=100.0)
    signal = _estimate(*fitted, feature_vector(candles, last))
    return blend * signal, blend, len(examples)


def run(now: datetime, ledger: Path, report: Path, scores_ledger: Path | None = None) -> dict:
    if now.tzinfo is None:
        raise ValueError("UTC-aware issuance time required")
    candles = fetch(now)
    origin, current = candles[-1]
    existing = ledger_rows(ledger)
    keys = {(r["version"], r["origin_hour_utc"], r["horizon_hours"]) for r in existing}
    new = []
    returns = [math.log(b[1] / a[1]) for a, b in pairwise(candles)]
    volatility = statistics.pstdev(returns[-168:])
    for horizon in HORIZONS:
        if (VERSION, origin.isoformat(), horizon) in keys:
            continue
        signal, blend, examples = train(candles, horizon)
        forecast = current * math.exp(max(-0.2, min(0.2, signal)))
        new.append(
            {
                "version": VERSION,
                "issued_at_utc": now.astimezone(UTC).isoformat(),
                "origin_hour_utc": origin.isoformat(),
                "target_hour_utc": (origin + timedelta(hours=horizon)).isoformat(),
                "target_close_utc": (origin + timedelta(hours=horizon + 1)).isoformat(),
                "horizon_hours": horizon,
                "origin_close_usd": current,
                "forecast_usd": forecast,
                "persistence_usd": current,
                "observed_volatility_hourly": volatility,
                "training_hours": len(candles),
                "resolved_training_examples": examples,
                "holdout_selected_blend": blend,
                "source": "coinbase:exchange:BTC-USD:1h:close",
                "research_only": True,
            }
        )
    if new:
        ledger.parent.mkdir(parents=True, exist_ok=True)
        with ledger.open("a", encoding="utf-8") as output:
            for row in new:
                output.write(json.dumps(row, sort_keys=True) + "\n")
    prices = {hour.isoformat(): price for hour, price in candles}
    scores_ledger = scores_ledger or ledger.with_name("hourly_scores.jsonl")
    prior_scores = ledger_rows(scores_ledger)
    scored_keys = {(r["version"], r["origin_hour_utc"], r["horizon_hours"]) for r in prior_scores}
    newly_scored = []
    for row in [*existing, *new]:
        key = (row["version"], row["origin_hour_utc"], row["horizon_hours"])
        target_close = datetime.fromisoformat(
            row.get("target_close_utc")
            or (datetime.fromisoformat(row["target_hour_utc"]) + timedelta(hours=1)).isoformat()
        )
        if (
            key in scored_keys
            or row["target_hour_utc"] not in prices
            or target_close > now.astimezone(UTC)
            or datetime.fromisoformat(row["issued_at_utc"]) >= target_close
        ):
            continue
        actual = prices[row["target_hour_utc"]]
        newly_scored.append(
            {
                "version": row["version"],
                "origin_hour_utc": row["origin_hour_utc"],
                "horizon_hours": row["horizon_hours"],
                "target_hour_utc": row["target_hour_utc"],
                "target_close_utc": target_close.isoformat(),
                "actual_close_usd": actual,
                "model_absolute_error_usd": abs(row["forecast_usd"] - actual),
                "persistence_absolute_error_usd": abs(row["persistence_usd"] - actual),
                "scored_at_utc": now.astimezone(UTC).isoformat(),
            }
        )
        scored_keys.add(key)
    if newly_scored:
        scores_ledger.parent.mkdir(parents=True, exist_ok=True)
        with scores_ledger.open("a", encoding="utf-8") as output:
            for row in newly_scored:
                output.write(json.dumps(row, sort_keys=True) + "\n")
    scores = {}
    for horizon in HORIZONS:
        resolved = [
            row
            for row in [*prior_scores, *newly_scored]
            if row["version"] == VERSION and row["horizon_hours"] == horizon
        ]
        scores[str(horizon)] = {
            "resolved": len(resolved),
            "model_mae_usd": (
                statistics.mean(row["model_absolute_error_usd"] for row in resolved)
                if resolved
                else None
            ),
            "persistence_mae_usd": (
                statistics.mean(row["persistence_absolute_error_usd"] for row in resolved)
                if resolved
                else None
            ),
        }
    result = {
        "status": "HOURLY_PROSPECTIVE",
        "model_version": VERSION,
        "origin_hour_utc": origin.isoformat(),
        "issued": new,
        "newly_scored": len(newly_scored),
        "scores": scores,
        "research_only": True,
        "limitations": "No trading or profitability claim; evaluate only future issued forecasts.",
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--scores-ledger", type=Path)
    args = parser.parse_args()
    result = run(datetime.now(UTC), args.ledger, args.report, args.scores_ledger)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
