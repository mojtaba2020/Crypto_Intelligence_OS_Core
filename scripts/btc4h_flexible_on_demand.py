"""On-demand four-hour BTC/USD research. Separate from the fixed 180-slot study."""

from __future__ import annotations

import argparse
import json
import math
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from crypto_intelligence_os.hybrid_forecasting import _estimate, _fit
from scripts.alpha_coinbase_historical_replay import fetch_candles, iso
from scripts.alpha_interaction_candidate import _independent_interaction_projection
from scripts.alpha_volume_confirmation import (
    HourlyVolumeBar,
    _interaction_residual,
    volume_confirmation_features,
)
from scripts.alpha_volume_historical_replay import fetch_public_hourly_close_volume

MODELS = ("volume_interaction", "price_plus_volume", "price_only", "persistence")
VERSION = "btc4h-flexible-v1-ridge100"
HISTORY_DAYS = 10

def read(path):
    return (
        [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
        if path.exists()
        else []
    )

def append(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
        f.flush()
        os.fsync(f.fileno())

def features(hourly, origin, fetched):
    starts = [origin - timedelta(hours=25-i) for i in range(25)]
    if any(t not in hourly for t in starts):
        return None
    bars = tuple(
        HourlyVolumeBar(
            bar_open_utc=t,
            close_usd=hourly[t][0],
            base_volume_btc=hourly[t][1],
            first_observed_at_utc=fetched,
        )
        for t in starts
    )
    return volume_confirmation_features(bars, issued_at_utc=fetched), bars[-1].close_usd

def issue(ledger):
    start = datetime.now(UTC)
    # Use the last CLOSED hourly bar only. The present hour is never treated as complete.
    origin = start.replace(minute=0, second=0, microsecond=0)
    target_open = (start + timedelta(hours=4)).replace(
        minute=(start.minute // 5) * 5,
        second=0,
        microsecond=0,
    ) + timedelta(minutes=5)
    target_close = target_open + timedelta(minutes=5)
    hourly = fetch_public_hourly_close_volume(
        origin - timedelta(days=HISTORY_DAYS, hours=25), origin
    )
    fetched = datetime.now(UTC)
    current = features(hourly, origin, fetched)
    if current is None:
        raise RuntimeError("Incomplete hourly history; no forecast")
    targets = fetch_candles(
        origin - timedelta(days=HISTORY_DAYS) + timedelta(hours=4, minutes=10),
        origin - timedelta(hours=4),
        granularity=300,
    )
    fetched_targets = datetime.now(UTC)
    training = []
    for i in range(HISTORY_DAYS*6):
        prior = origin - timedelta(days=HISTORY_DAYS) + timedelta(hours=4*i)
        if prior > origin - timedelta(hours=8):
            break
        result = features(hourly, prior, fetched)
        target = prior + timedelta(hours=4, minutes=10)
        if result is None or target not in targets or target + timedelta(minutes=5) > start:
            continue
        x, ref = result
        training.append((x, math.log(targets[target]/ref)))
    if len(training) < 30:
        raise RuntimeError("Insufficient mature training examples; no forecast")
    projection, enabled = _independent_interaction_projection(training)
    full = [((m,v,_interaction_residual(m,v,z,projection,enabled)),y) for (m,v,z),y in training]
    additive = [((m,v),y) for (m,v,z),y in training]
    momentum = [((m,),y) for (m,v,z),y in training]
    (m,v,z), reference = current
    returns = {
        "volume_interaction": _estimate(
            *_fit(full, ridge=100.0),
            (m, v, _interaction_residual(m, v, z, projection, enabled)),
        ),
        "price_plus_volume": _estimate(*_fit(additive,ridge=100.0),(m,v)),
        "price_only": _estimate(*_fit(momentum,ridge=100.0),(m,)),
        "persistence": 0.0,
    }
    if any(not math.isfinite(x) or abs(x) >= 0.5 for x in returns.values()):
        raise RuntimeError("Unsafe forecast output")
    issued = datetime.now(UTC)
    if issued >= target_open:
        raise RuntimeError("Target began before publication")
    # Approximate 4h horizon: next full 5-minute target bar after now+4h.
    row = dict(
        version=VERSION,
        issued_at_utc=iso(issued),
        target_5m_bar_open_utc=iso(target_open),
        target_5m_close_utc=iso(target_close),
        origin_hour_utc=iso(origin),
        reference_usd=reference,
        price_forecasts_usd={k: reference * math.exp(v) for k, v in returns.items()},
        training_count=len(training),
        data_received_at_utc=iso(fetched),
        target_training_received_at_utc=iso(fetched_targets),
        research_only=True,
        not_a_trade=True,
        independent_time_witness=False,
        pinned_model_sha="9de38d2c30c892d6e7ef3d65a0ee5a6507f77dc9",
    )
    if len([x for x in read(ledger) if x["issued_at_utc"][:10] == iso(issued)[:10]]) >= 4:
        raise RuntimeError("Four forecasts already issued today (UTC)")
    append(ledger,row)
    print(json.dumps(dict(status="issued",forecast=row),sort_keys=True))

def score(ledger,scores):
    existing=read(scores)
    done={r["issued_at_utc"] for r in existing}
    now=datetime.now(UTC)
    for row in read(ledger):
        if row["issued_at_utc"] in done:
            continue
        close=datetime.fromisoformat(row["target_5m_close_utc"].replace("Z","+00:00"))
        if close>now or now-close>timedelta(days=39):
            continue
        opened=datetime.fromisoformat(row["target_5m_bar_open_utc"].replace("Z","+00:00"))
        candles=fetch_candles(opened,close,granularity=300)
        if opened not in candles:
            continue
        actual=candles[opened]
        ref=row["reference_usd"]
        append(
            scores,
            dict(
                issued_at_utc=row["issued_at_utc"],
                target_5m_close_utc=row["target_5m_close_utc"],
                actual_close_usd=actual,
                absolute_errors_usd={
                    k: abs(v - actual) for k, v in row["price_forecasts_usd"].items()
                },
                direction_correct={
                    k: None if abs(v - ref) < 1e-9 or actual == ref
                    else (v > ref) == (actual > ref)
                    for k, v in row["price_forecasts_usd"].items()
                },
                scored_at_utc=iso(datetime.now(UTC)),
            ),
        )
        print("scored",row["issued_at_utc"])

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--phase",choices=["issue","score"],required=True)
    p.add_argument("--ledger",type=Path,default=Path("research/btc4h_flexible_forecasts.jsonl"))
    p.add_argument("--scores",type=Path,default=Path("research/btc4h_flexible_scores.jsonl"))
    args=p.parse_args()
    (issue(args.ledger) if args.phase=="issue" else score(args.ledger,args.scores))
