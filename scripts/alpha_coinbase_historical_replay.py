"""Single, bounded BTC historical 4h research diagnostic (NOT a live backtest).

WARNING: Coinbase historic candles fetched today contain no original first-
receipt timestamps. We use an OPTIMISTIC HYPOTHETICAL 1-second-after-close
availability assumption solely to test numerical walk-forward plumbing.
Results are contaminated retrospective exploration, never Stage-6 evidence.
No orders, API keys, adaptive parameter search, or protected-OOS reads.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from scripts.alpha_4h_training_bridge import (
    FiveMinuteTarget,
    make_matured_example,
    walk_forward_development_diagnostic,
)
from scripts.alpha_interaction_candidate import HourlyClose

API = "https://api.exchange.coinbase.com/products/BTC-USD/candles"
RIDGE = 100.0  # fixed a priori; do not tune on these outcomes
GRANULARITIES = (300, 3600)
USER_AGENT = "Crypto-Intelligence-OS/alpha-retrospective-research"
ASSUMED_AFTER_CLOSE = timedelta(seconds=1)


def iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def fetch_candles(
    start: datetime, end: datetime, *, granularity: int
) -> dict[datetime, float]:
    """Fetch bounded PUBLIC Coinbase history, retaining exact bucket-open clocks.

    No timestamp from this API proves that candle content was known at that
    historic instant. No missing bucket is imputed or filled from the future.
    """
    if granularity not in GRANULARITIES or not start < end:
        raise ValueError("invalid market data window or bar granularity")
    if (end - start) > timedelta(days=40):
        raise ValueError("research-only cap is 40 days")
    candles: dict[datetime, float] = {}
    cursor = start
    while cursor < end:
        stop = min(cursor + timedelta(seconds=granularity * 250), end)
        query = urllib.parse.urlencode(
            {"start": iso(cursor), "end": iso(stop), "granularity": granularity}
        )
        request = urllib.request.Request(  # noqa: S310 -- fixed HTTPS Coinbase endpoint
            f"{API}?{query}", headers={"User-Agent": USER_AGENT}
        )
        for attempt in range(4):
            try:
                with urllib.request.urlopen(request, timeout=35) as response:  # noqa: S310
                    data: Any = json.load(response)
                break
            except urllib.error.HTTPError as exc:
                if exc.code not in (429, 500, 502, 503, 504) or attempt == 3:
                    raise
                time.sleep(0.8 * 2**attempt)
            except (TimeoutError, urllib.error.URLError):
                if attempt == 3:
                    raise
                time.sleep(0.8 * 2**attempt)
        if not isinstance(data, list):
            raise ValueError("Coinbase returned non-array OHLCV")
        for item in data:
            if not isinstance(item, list) or len(item) < 5:
                raise ValueError("malformed public candle")
            opened = datetime.fromtimestamp(int(item[0]), UTC)
            close = float(item[4])
            if not cursor <= opened < stop:
                continue  # Coinbase may return a boundary candle
            if (
                int(opened.timestamp()) % granularity != 0
                or not math.isfinite(close)
                or close <= 0
            ):
                raise ValueError("invalid or misaligned historical candle")
            if opened in candles and candles[opened] != close:
                raise ValueError("conflicting duplicate historical close")
            candles[opened] = close
        cursor = stop
        time.sleep(0.15)
    return candles


def _digest(candles: dict[datetime, float]) -> str:
    payload = json.dumps(
        [[iso(ts), price] for ts, price in sorted(candles.items())],
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def run_replay(
    hourly: dict[datetime, float],
    fivemin: dict[datetime, float],
    *,
    start: datetime,
    end: datetime,
) -> dict[str, Any]:
    """Deterministic retrospective development diagnostic, not prospective alpha."""
    if start.utcoffset() != timedelta(0) or end.utcoffset() != timedelta(0):
        raise ValueError("replay range must use aware UTC")
    if (
        any((start.hour, start.minute, start.second, start.microsecond))
        or any((end.hour, end.minute, end.second, end.microsecond))
        or (end - start) < timedelta(days=7)
        or (end - start) > timedelta(days=38)
    ):
        raise ValueError("replay requires 7..38 complete UTC days")
    planned = int((end - start) / timedelta(hours=4))
    examples = []
    rejected = {"missing_1h": 0, "missing_5m": 0}
    cursor = start
    last_fit = end + timedelta(days=1)
    while cursor < end:
        hourly_starts = [
            cursor - timedelta(hours=(25 - i)) for i in range(25)
        ]
        if any(t not in hourly for t in hourly_starts):
            rejected["missing_1h"] += 1
            cursor += timedelta(hours=4)
            continue
        target_open = cursor + timedelta(hours=4, minutes=10)
        if target_open not in fivemin:
            rejected["missing_5m"] += 1
            cursor += timedelta(hours=4)
            continue
        bars = [
            HourlyClose(
                bar_open_utc=t,
                close_usd=hourly[t],
                first_observed_at_utc=t + timedelta(hours=1) + ASSUMED_AFTER_CLOSE,
            )
            for t in hourly_starts
        ]
        target = FiveMinuteTarget(
            bar_open_utc=target_open,
            close_usd=fivemin[target_open],
            first_observed_at_utc=target_open + timedelta(minutes=5) + ASSUMED_AFTER_CLOSE,
        )
        examples.append(
            make_matured_example(
                bars,
                origin_utc=cursor,
                issued_at_utc=cursor + timedelta(minutes=10),
                target=target,
                fit_at_utc=last_fit,
            )
        )
        cursor += timedelta(hours=4)
    if len(examples) < 32:
        raise ValueError("too few complete historical origins to form and test a model")
    report = walk_forward_development_diagnostic(examples, ridge=RIDGE)
    scores = report.scored_rows
    if not scores:
        raise ValueError("no evaluable walk-forward predictions")
    means = {
        "candidate": report.mean_candidate_abs_log_error,
        "ablation": report.mean_ablation_abs_log_error,
        "placebo": report.mean_placebo_abs_log_error,
        "persistence": report.mean_persistence_abs_log_error,
    }
    persistence = report.mean_persistence_abs_log_error
    candidate = report.mean_candidate_abs_log_error
    if candidate is None or persistence is None:
        raise ValueError("no historical comparisons available")
    if persistence <= 0:
        raise ValueError("historical sample has no price movements")
    direction = {}
    for variant in ("candidate", "ablation", "placebo"):
        predictions = [
            getattr(row, f"{variant}_predicted_log_return") for row in scores
        ]
        nonflat = [
            (prediction, row.realized_log_return)
            for prediction, row in zip(predictions, scores, strict=True)
            if abs(prediction) > 1e-12
        ]
        correct = sum(
            (predicted > 0) == (realized > 0)
            for predicted, realized in nonflat
            if realized != 0
        )
        assessed = sum(realized != 0 for _, realized in nonflat)
        direction[variant] = {
            "forecasts_nonflat": len(nonflat),
            "assessed_nonflat_actual": assessed,
            "correct_nonflat": correct,
            "conditional_accuracy_pct": round(100 * correct / assessed, 3)
            if assessed else None,
            "all_scored_denominator": len(scores),
        }
    return {
        "status": "HISTORICAL_EXPLORATION_ONLY_NOT_VALIDATED_ALPHA",
        "pair": "Coinbase Exchange BTC-USD",
        "window_start_utc": iso(start),
        "window_end_exclusive_utc": iso(end),
        "horizon_convention": "S+4h15m five-minute bar close",
        "scheduled_slots": planned,
        "complete_historical_rows": len(examples),
        "rejected_origins": rejected,
        "cold_start_rows": report.cold_start_rows,
        "scored_historical_origins": len(scores),
        "interaction_applied": sum(row.interaction_applied for row in scores),
        "mean_absolute_log_price_error": means,
        "candidate_relative_error_reduction_pct": round(
            100 * (persistence - candidate) / persistence, 4
        ),
        "direction_secondary_nonflat": direction,
        "hourly_candles_downloaded": len(hourly),
        "five_minute_candles_downloaded": len(fivemin),
        "hourly_snapshot_digest_sha256": _digest(hourly),
        "five_minute_snapshot_digest_sha256": _digest(fivemin),
        "fixed_ridge": RIDGE,
        "data_first_observed_authenticated": False,
        "forecast_original_publication_authenticated": False,
        "hypothetical_issue_at": "S+10m; computed retrospectively, NOT actually issued then",
        "hypothetical_source_receipt": "bar close + 1 second; NOT actual archival vintage",
        "model_status": "NO_RUN_NO_FREEZE_FOR_SCIENTIFIC_CONFIRMATION",
        "limitations": (
            "One exposed historical window; hypothetical first-observed stamps; "
            "nonstationarity, serial dependence, data revisions, sample selection "
            "and multiple testing not independently controlled; zero trading claims."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2026-10-01")
    parser.add_argument("--end", default="2026-10-29")
    parser.add_argument("--output", type=Path, default=Path("alpha_4h_exploratory.json"))
    args = parser.parse_args()
    start = datetime.fromisoformat(args.start).replace(tzinfo=UTC)
    end = datetime.fromisoformat(args.end).replace(tzinfo=UTC)
    hourly = fetch_candles(start - timedelta(hours=25), end, granularity=3600)
    five_minute = fetch_candles(
        start + timedelta(hours=4, minutes=10),
        end + timedelta(minutes=15),
        granularity=300,
    )
    summary = run_replay(hourly, five_minute, start=start, end=end)
    summary["retrieved_at_utc"] = iso(datetime.now(UTC))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
