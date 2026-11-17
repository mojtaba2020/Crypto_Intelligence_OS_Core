"""One-shot, exposed-October BTC 4h classical challengers (retrospective only).

Fetches public Coinbase historical candles TODAY. It never invents original
issue/first-observed timestamps, so results cannot prove historical as-of
availability, prospective validity, independent alpha, or production readiness.
No live model updates, trading, credentials, scheduling, or protected OOS.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from scripts.btc4h_challenger_tournament import ALL_MODELS, CANDIDATES, MAX_EVAL, MIN_TRAIN, _model

API = "https://api.exchange.coinbase.com/products/BTC-USD/candles"
USER_AGENT = "Crypto-Intelligence-OS/0.3 research (public Coinbase 4h retrospective)"
START = datetime(2026, 10, 1, tzinfo=UTC)
END = datetime(2026, 10, 18, tzinfo=UTC)
MAX_RESPONSE_BYTES = 120_000


def iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _positive(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError("candle value not numeric")
    v = float(value)
    if not math.isfinite(v) or v <= 0:
        raise ValueError("candle value not finite and positive")
    return v


def fetch_buckets(
    start: datetime, end: datetime, granularity: int
) -> dict[datetime, tuple[float, float]]:
    """Bounded public historical download. Returns close USD and BTC base volume.

    This read's timestamp is NOW, not the original time a historical value
    first appeared publicly. Do NOT invent an old receipt from candle close.
    """
    if granularity not in (300, 3600) or not (
        START - timedelta(days=2) <= start < end <= END + timedelta(days=2)
    ):
        raise ValueError("download bounds outside predeclared exposed research interval")
    if start.utcoffset() != timedelta(0) or end.utcoffset() != timedelta(0):
        raise ValueError("UTC required")
    out: dict[datetime, tuple[float, float]] = {}
    cursor = start
    while cursor < end:
        stop = min(end, cursor + timedelta(seconds=200 * granularity))
        query = urllib.parse.urlencode(
            {"start": iso(cursor), "end": iso(stop), "granularity": granularity}
        )
        url = f"{API}?{query}"
        request = urllib.request.Request(  # noqa: S310 - hardcoded HTTPS Coinbase host.
            url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
        )
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=25) as response:  # noqa: S310
                    final = urllib.parse.urlsplit(response.geturl())
                    if final.scheme != "https" or final.hostname != "api.exchange.coinbase.com":
                        raise ValueError("unexpected redirect from pinned Coinbase host")
                    blob = response.read(MAX_RESPONSE_BYTES + 1)
                if len(blob) > MAX_RESPONSE_BYTES:
                    raise ValueError("oversized public response")
                records = json.loads(blob)
                if not isinstance(records, list):
                    raise ValueError("Coinbase response must be list")
                break
            except urllib.error.HTTPError as exc:
                if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                    raise
                time.sleep(0.7 * 2**attempt)
            except (TimeoutError, urllib.error.URLError):
                if attempt == 2:
                    raise
                time.sleep(0.7 * 2**attempt)
        for item in records:
            if not isinstance(item, list) or len(item) != 6:
                raise ValueError("invalid public OHLCV record")
            try:
                ts = int(item[0])
                stamp = datetime.fromtimestamp(ts, UTC)
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError("invalid candle timestamp") from exc
            if not cursor <= stamp < stop:
                continue
            if ts % granularity:
                raise ValueError("noncanonical candle")
            close, volume = _positive(item[4]), _positive(item[5])
            value = (close, volume)
            if stamp in out and out[stamp] != value:
                raise ValueError("conflicting duplicate historical candle")
            out[stamp] = value
        cursor = stop
        time.sleep(0.18)
    return out


def build_rows(
    hourly: dict[datetime, tuple[float, float]],
    five_minute: dict[datetime, tuple[float, float]],
    start: datetime = START,
    end: datetime = END,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    if start != START or end != END:
        raise ValueError("research replay is pinned to one already-exposed window")
    counters = {"missing_hourly": 0, "missing_target": 0}
    rows: list[dict[str, Any]] = []
    origin = start
    while origin < end:
        opens = [origin - timedelta(hours=25 - i) for i in range(25)]
        if any(stamp not in hourly for stamp in opens):
            counters["missing_hourly"] += 1
        else:
            target_open = origin + timedelta(hours=4, minutes=10)
            if target_open not in five_minute:
                counters["missing_target"] += 1
            else:
                bars = [hourly[stamp] for stamp in opens]
                momentum = math.log(bars[-1][0] / bars[-5][0])
                recent = math.fsum(row[1] for row in bars[-4:])
                before = math.fsum(row[1] for row in bars[1:21])
                shock = math.log(recent / (before / 5.0))
                if not all(
                    math.isfinite(x) and abs(x) <= 20 for x in (momentum, shock, momentum * shock)
                ):
                    raise ValueError("nonfinite or extreme retrospective features")
                reference = bars[-1][0]
                actual = five_minute[target_open][0]
                rows.append(
                    {
                        "origin": origin,
                        "target_close": target_open + timedelta(minutes=5),
                        "x": [momentum, shock, momentum * shock],
                        "reference": reference,
                        "actual": actual,
                    }
                )
        origin += timedelta(hours=4)
    return rows, counters


def evaluate_retrospective(rows: list[dict[str, Any]], model_factory: Any = None) -> dict[str, Any]:
    """Exploratory maths only; historical as-of data availability is UNPROVEN."""
    factory = model_factory or _model
    if not 2 <= len(rows) <= 150:
        raise ValueError("retrospective row count out of bounds")
    if any(rows[i]["origin"] >= rows[i + 1]["origin"] for i in range(len(rows) - 1)):
        raise ValueError("non-increasing origin")
    errors: dict[str, list[float]] = {name: [] for name in ALL_MODELS}
    direction: dict[str, list[bool]] = {name: [] for name in CANDIDATES}
    fold_ids: list[str] = []
    earliest_training_count: int | None = None
    for pos, current in enumerate(rows):
        train = [old for old in rows[:pos] if old["target_close"] < current["origin"]]
        if len(train) < MIN_TRAIN:
            continue
        if len(fold_ids) >= MAX_EVAL:
            break
        if earliest_training_count is None:
            earliest_training_count = len(train)
        x = [old["x"] for old in train]
        y = [math.log(old["actual"] / old["reference"]) for old in train]
        realized = math.log(current["actual"] / current["reference"])
        forecasts: dict[str, float] = {"persistence": 0.0}
        for name in CANDIDATES:
            est = factory(name)
            est.fit(x, y)
            pred = float(est.predict([current["x"]])[0])
            if not math.isfinite(pred) or abs(pred) >= 0.5:
                raise ValueError("invalid challenger estimate")
            forecasts[name] = pred
        for name, pred in forecasts.items():
            errors[name].append(abs(pred - realized))
            if name != "persistence" and pred != 0 and realized != 0:
                direction[name].append((pred > 0) == (realized > 0))
        fold_ids.append(iso(current["origin"]))
    if len(fold_ids) == 0:
        raise ValueError("no folds with 30 complete matured historical training examples")
    metrics = {}
    for name in ALL_MODELS:
        values = errors[name]
        correct = sum(direction.get(name, []))
        eligible = len(direction.get(name, []))
        metrics[name] = {
            "mean_absolute_log_error": statistics.mean(values),
            "paired_mean_gain_vs_persistence": statistics.mean(
                a - b for a, b in zip(errors["persistence"], values, strict=True)
            ),
            "correct_direction": correct,
            "nonflat_evaluable_direction": eligible,
            "conditional_direction_accuracy": correct / eligible if eligible else None,
            "correct_over_all_scored_origins": correct / len(values),
        }
    return {
        "mode": "EXPOSED_OCTOBER_2026_RETROSPECTIVE_EXPLORATION",
        "scientific_authorization": "NO_PROMOTION_NO_FREEZE_NOT_PROSPECTIVE",
        "historical_feature_vintage_authenticated": False,
        "original_forecast_issuance_exists": False,
        "evaluation_count": len(fold_ids),
        "first_evaluation_origin_utc": fold_ids[0],
        "last_evaluation_origin_utc": fold_ids[-1],
        "earliest_mature_training_count": earliest_training_count,
        "model_metrics": metrics,
        "not_for_trade": True,
    }


def digest(rows: dict[datetime, tuple[float, float]]) -> str:
    payload = json.dumps(
        [[iso(k), price, volume] for k, (price, volume) in sorted(rows.items())],
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    hourly = fetch_buckets(START - timedelta(hours=25), END, 3600)
    targets = fetch_buckets(
        START + timedelta(hours=4, minutes=10), END + timedelta(minutes=15), 300
    )
    retrieved_at = datetime.now(UTC)
    rows, rejects = build_rows(hourly, targets)
    report = evaluate_retrospective(rows)
    report.update(
        {
            "retrieved_at_utc": iso(retrieved_at),
            "source": "Coinbase Exchange BTC-USD public historical 1h and 5m candles",
            "source_available_then": "UNVERIFIABLE_HISTORY_RETRIEVED_TODAY",
            "source_hourly_sha256": digest(hourly),
            "source_5min_sha256": digest(targets),
            "public_hourly_candles": len(hourly),
            "public_five_minute_candles": len(targets),
            "window_start_utc": iso(START),
            "window_end_exclusive_utc": iso(END),
            "expected_four_hour_slots": int((END - START) / timedelta(hours=4)),
            "complete_slots": len(rows),
            "incomplete_slots": rejects,
            "note": (
                "This exposed interval has already influenced earlier development. "
                "The API cannot prove its historical original publication time or revisions. "
                "Numerical exploration only: NO ALPHA and NO model promotion."
            ),
        }
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
