"""Forward-only BTC 4h shadow forecasts: future issue, future scoring.

Research only. Market data are first retrieved for THIS run, not retroactively
assigned historical first-seen times. Previous closed historical candles may
train a new model as-of today, but they do not constitute past issued forecasts.
No orders, trading, protected-OOS evaluation, independent witness, or alpha claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from scripts.alpha_coinbase_historical_replay import fetch_candles, iso
from scripts.alpha_interaction_candidate import _independent_interaction_projection
from scripts.alpha_volume_confirmation import (
    HourlyVolumeBar,
    _interaction_residual,
    volume_confirmation_features,
)
from scripts.alpha_volume_historical_replay import fetch_public_hourly_close_volume

from crypto_intelligence_os.hybrid_forecasting import _estimate, _fit

VERSION = "btc4h-volume-shadow-v1-ridge100"
RIDGE = 100.0
HISTORY_DAYS = 10
MIN_TRAINING = 30
MODEL_NAMES = ("volume_interaction", "price_plus_volume", "price_only", "persistence")
EARLIEST_PREFETCH_MINUTE = 8
MAX_EARLY_WAIT_SECONDS = 120


def utc(dt: datetime) -> datetime:
    if not isinstance(dt, datetime) or dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError("event time must be aware UTC")
    return dt


def origin_at(dt: datetime) -> datetime:
    utc(dt)
    return dt.replace(hour=(dt.hour // 4) * 4, minute=0, second=0, microsecond=0)


def in_issue_window(at: datetime) -> bool:
    s = origin_at(at)
    return s + timedelta(minutes=10) <= at <= s + timedelta(minutes=15)


def in_prefetch_window(at: datetime) -> bool:
    """Fetch only in the current origin's S+8m..S+15m interval."""
    s = origin_at(at)
    return s + timedelta(minutes=EARLIEST_PREFETCH_MINUTE) <= at <= s + timedelta(
        minutes=15
    )


def _digest(mapping: dict[datetime, Any]) -> str:
    rows = [[iso(t), value] for t, value in sorted(mapping.items())]
    return hashlib.sha256(
        json.dumps(rows, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _bars(
    hourly: dict[datetime, tuple[float, float]],
    origin: datetime,
    fetched_at: datetime,
) -> tuple[HourlyVolumeBar, ...] | None:
    starts = [origin - timedelta(hours=25 - j) for j in range(25)]
    if any(t not in hourly for t in starts):
        return None
    bars = tuple(
        HourlyVolumeBar(
            bar_open_utc=t,
            close_usd=hourly[t][0],
            base_volume_btc=hourly[t][1],
            first_observed_at_utc=fetched_at,
        )
        for t in starts
    )
    return bars


def calculate_issue(
    *,
    issued_at: datetime,
    hourly_fetched_at: datetime,
    target_fetched_at: datetime,
    hourly: dict[datetime, tuple[float, float]],
    closed_targets: dict[datetime, float],
    code_sha: str = "local-research",
) -> dict[str, Any]:
    """Construct 4h predictions as of REAL issue time from currently received data.

    Historical training features/outcomes are calculated retrospectively AS OF
    this actual retrieval, without fabricating historical issuance timestamps.
    The immediately preceding 4h target ending S+15m is always excluded.
    """
    utc(issued_at)
    utc(hourly_fetched_at)
    utc(target_fetched_at)
    if not in_issue_window(issued_at):
        raise ValueError("MISS_ISSUE_WINDOW: no retrospective forecast issuance")
    origin = origin_at(issued_at)
    if hourly_fetched_at > issued_at or target_fetched_at > issued_at:
        raise ValueError("market data must be received by actual issue time")
    if hourly_fetched_at < origin or target_fetched_at < origin:
        raise ValueError("this run must collect market history after its live origin")
    current_bars = _bars(hourly, origin, hourly_fetched_at)
    if current_bars is None:
        raise ValueError("current 25 hourly OHLCV bars incomplete")
    current = volume_confirmation_features(current_bars, issued_at_utc=issued_at)
    reference = current_bars[-1].close_usd
    training: list[tuple[tuple[float, float, float], float]] = []
    missing_hourly = 0
    missing_target = 0
    prior = origin - timedelta(days=HISTORY_DAYS)
    # Explicitly exclude the S-4h origin: its S+15m target is NOT yet mature
    # when this issuance occurs within [S+10m,S+15m].
    while prior <= origin - timedelta(hours=8):
        target_open = prior + timedelta(hours=4, minutes=10)
        target_end = target_open + timedelta(minutes=5)
        bars = _bars(hourly, prior, hourly_fetched_at)
        if bars is None:
            missing_hourly += 1
        elif target_open not in closed_targets:
            missing_target += 1
        elif target_end <= target_fetched_at and target_end <= issued_at:
            x = volume_confirmation_features(bars, issued_at_utc=issued_at)
            target_close = closed_targets[target_open]
            if not math.isfinite(target_close) or target_close <= 0:
                raise ValueError("invalid historical five-minute target close")
            training.append((x, math.log(target_close / bars[-1].close_usd)))
        else:
            raise ValueError("unmatured historical label may not train this issue")
        prior += timedelta(hours=4)

    if len(training) < MIN_TRAINING:
        raise ValueError("INSUFFICIENT_MATURE_TRAINING")
    if len(training) > 512:
        raise ValueError("unexpected unbounded training")
    projection, enabled = _independent_interaction_projection(training)
    full = [
        ((m, v, _interaction_residual(m, v, z, projection, enabled)), y)
        for (m, v, z), y in training
    ]
    additive = [((m, v), y) for (m, v, _), y in training]
    momentum = [((m,), y) for (m, _, _), y in training]
    m, v, z = current
    returns = {
        "volume_interaction": _estimate(
            *_fit(full, ridge=RIDGE),
            (m, v, _interaction_residual(m, v, z, projection, enabled)),
        ),
        "price_plus_volume": _estimate(*_fit(additive, ridge=RIDGE), (m, v)),
        "price_only": _estimate(*_fit(momentum, ridge=RIDGE), (m,)),
        "persistence": 0.0,
    }
    if not all(math.isfinite(x) and abs(x) < 0.5 for x in returns.values()):
        raise ValueError("nonfinite or unbounded shadow return")
    prices = {name: reference * math.exp(ret) for name, ret in returns.items()}
    if not all(math.isfinite(price) and price > 0 for price in prices.values()):
        raise ValueError("nonfinite USD forecast")
    return {
        "version": VERSION,
        "origin_utc": iso(origin),
        "issued_at_utc": iso(issued_at),
        "hourly_data_collected_at_utc": iso(hourly_fetched_at),
        "target_training_data_collected_at_utc": iso(target_fetched_at),
        "target_5m_bar_open_utc": iso(origin + timedelta(hours=4, minutes=10)),
        "target_5m_close_utc": iso(origin + timedelta(hours=4, minutes=15)),
        "origin_reference_close_usd": reference,
        "return_forecasts": returns,
        "price_forecasts_usd": prices,
        "mature_historical_training_examples": len(training),
        "missing_training_hourly_origins": missing_hourly,
        "missing_training_target_origins": missing_target,
        "interaction_active": enabled,
        "source": "Coinbase Exchange BTC-USD 1h close+base-volume, 5m target",
        "source_hourly_digest_sha256": _digest(hourly),
        "source_training_target_digest_sha256": _digest(closed_targets),
        "code_commit_sha": code_sha,
        "independent_source_witness": False,
        "research_only": True,
        "not_a_trade": True,
    }


def calculate_score(
    forecast: dict[str, Any], *, actual: float, target_received_at: datetime
) -> dict[str, Any]:
    """Score ONLY after the historic issued row's target bar has really closed."""
    utc(target_received_at)
    if forecast["version"] != VERSION or not forecast.get("research_only"):
        raise ValueError("invalid version or unsafe forecast ledger")
    issued = datetime.fromisoformat(forecast["issued_at_utc"].replace("Z", "+00:00"))
    origin = datetime.fromisoformat(forecast["origin_utc"].replace("Z", "+00:00"))
    target_open = datetime.fromisoformat(forecast["target_5m_bar_open_utc"].replace("Z", "+00:00"))
    target_close = datetime.fromisoformat(forecast["target_5m_close_utc"].replace("Z", "+00:00"))
    if (
        origin_at(issued) != origin
        or not in_issue_window(issued)
        or target_open != origin + timedelta(hours=4, minutes=10)
        or target_close != target_open + timedelta(minutes=5)
        or not issued < target_close <= target_received_at
    ):
        raise ValueError("not a valid pre-target forward forecast")
    for key in ("hourly_data_collected_at_utc", "target_training_data_collected_at_utc"):
        when = datetime.fromisoformat(forecast[key].replace("Z", "+00:00"))
        if not origin <= when <= issued:
            raise ValueError("original market source evidence is temporally invalid")
    if not isinstance(actual, (int, float)) or isinstance(actual, bool):
        raise ValueError("invalid actual price")
    if not math.isfinite(actual) or actual <= 0:
        raise ValueError("invalid target close")
    ref = forecast["origin_reference_close_usd"]
    preds = forecast["price_forecasts_usd"]
    if not math.isfinite(ref) or ref <= 0:
        raise ValueError("invalid reference close")
    if set(preds) != set(MODEL_NAMES):
        raise ValueError("missing model comparators")
    if not all(math.isfinite(price) and price > 0 for price in preds.values()):
        raise ValueError("invalid forecast price")
    actual_return = math.log(actual / ref)
    losses = {name: abs(math.log(preds[name] / actual)) for name in MODEL_NAMES}
    direction = {
        name: (
            None
            if abs(math.log(preds[name] / ref)) <= 1e-12
            else (preds[name] > ref) == (actual > ref)
            if actual != ref
            else None
        )
        for name in MODEL_NAMES
    }
    return {
        "version": VERSION,
        "origin_utc": forecast["origin_utc"],
        "issued_at_utc": forecast["issued_at_utc"],
        "target_5m_bar_open_utc": forecast["target_5m_bar_open_utc"],
        "target_5m_close_utc": forecast["target_5m_close_utc"],
        "target_observed_at_utc": iso(target_received_at),
        "actual_close_usd": actual,
        "actual_log_return": actual_return,
        "absolute_log_price_errors": losses,
        "direction_correct_if_nonflat": direction,
        "research_only": True,
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            item = json.loads(line)
            if not isinstance(item, dict):
                raise ValueError("malformed JSONL entry")
            rows.append(item)
    return rows


def _append(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as out:
        out.write(json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n")
        out.flush()
        os.fsync(out.fileno())


def run_once(
    *,
    ledger: Path,
    score_ledger: Path,
    report: Path,
    code_sha: str = "local-research",
    clock: Callable[[], datetime] | None = None,
    sleeper: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    """One invocation: issue in the on-time slot, then score matured older rows.

    No backfilling missed origins. Missed slots are explicit, not fake forecasts.
    External runner/commit times are not independent third-party attestation.
    """
    get_time = clock if clock is not None else lambda: datetime.now(UTC)
    sleep_for = sleeper if sleeper is not None else time.sleep
    before = get_time()
    utc(before)
    existing = _read_jsonl(ledger)
    keys = [(r["version"], r["origin_utc"]) for r in existing]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate issued forecast origin in persistent ledger")
    current_origin = iso(origin_at(before))
    issued: dict[str, Any] | None = None
    status = "MISSED_ISSUE_WINDOW"
    if (VERSION, current_origin) in keys:
        status = "ALREADY_ISSUED"
    elif in_prefetch_window(before):
        origin = origin_at(before)
        hourly = fetch_public_hourly_close_volume(
            origin - timedelta(days=HISTORY_DAYS, hours=25), origin
        )
        hourly_read = get_time()
        targets = fetch_candles(
            origin - timedelta(days=HISTORY_DAYS) + timedelta(hours=4, minutes=10),
            origin - timedelta(hours=8) + timedelta(hours=4, minutes=15),
            granularity=300,
        )
        target_read = get_time()
        prepared_at = get_time()
        # The first scheduled attempt may prefetch at S+8m. We wait only
        # until S+10m and only for <=2 minutes. A missed deadline fails closed.
        if prepared_at < origin + timedelta(minutes=10):
            wait_seconds = (origin + timedelta(minutes=10) - prepared_at).total_seconds()
            if not 0 < wait_seconds <= MAX_EARLY_WAIT_SECONDS:
                raise ValueError("unexpected pre-issue wait duration")
            sleep_for(wait_seconds)
            prepared_at = get_time()
        if not in_issue_window(prepared_at) or origin_at(prepared_at) != origin:
            status = "MISSED_ISSUE_WINDOW_AFTER_FETCH"
        else:
            candidate = calculate_issue(
                issued_at=prepared_at,
                hourly_fetched_at=hourly_read,
                target_fetched_at=target_read,
                hourly=hourly,
                closed_targets=targets,
                code_sha=code_sha,
            )
            # Do NOT call a forecast "issued" at the pre-computation timestamp:
            # the real publish clock must be sampled AFTER model calculation.
            published_at = get_time()
            if not in_issue_window(published_at) or origin_at(published_at) != origin:
                status = "MISSED_ISSUE_WINDOW_AFTER_COMPUTE"
            else:
                candidate["issued_at_utc"] = iso(published_at)
                _append(ledger, candidate)
                issued = candidate
                status = "ISSUED_BEFORE_TARGET"
                existing.append(issued)
    previous_scores = _read_jsonl(score_ledger)
    scored_keys = [(r["version"], r["origin_utc"]) for r in previous_scores]
    if len(scored_keys) != len(set(scored_keys)):
        raise ValueError("duplicate score origin")
    scored_set = set(scored_keys)
    newly_scored = 0
    overdue_unavailable = 0
    for row in existing:
        key = (row["version"], row["origin_utc"])
        if key in scored_set:
            continue
        close = datetime.fromisoformat(row["target_5m_close_utc"].replace("Z", "+00:00"))
        if close > get_time():
            continue
        if get_time() - close > timedelta(days=39):
            overdue_unavailable += 1
            continue
        target_start = datetime.fromisoformat(row["target_5m_bar_open_utc"].replace("Z", "+00:00"))
        price_by_time = fetch_candles(
            target_start, target_start + timedelta(minutes=5), granularity=300
        )
        received = get_time()
        if target_start not in price_by_time:
            continue
        score = calculate_score(
            row, actual=price_by_time[target_start], target_received_at=received
        )
        _append(score_ledger, score)
        newly_scored += 1
        scored_set.add(key)

    result = {
        "research_status": status,
        "observed_run_at_utc": iso(before),
        "newly_issued": 1 if issued else 0,
        "newly_scored": newly_scored,
        "total_issued": len(existing),
        "total_scored": len(scored_set),
        "overdue_targets_unavailable_in_api_window": overdue_unavailable,
        "early_prefetch_started": bool(
            origin_at(before) + timedelta(minutes=EARLIEST_PREFETCH_MINUTE)
            <= before < origin_at(before) + timedelta(minutes=10)
        ),
        "real_forward_issue_proof_independent": False,
        "note": "Never backfill missed origins; GitHub schedule delivery is not guaranteed.",
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--score-ledger", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--code-sha", default="local-research")
    args = parser.parse_args()
    print(
        json.dumps(
            run_once(
                ledger=args.ledger,
                score_ledger=args.score_ledger,
                report=args.report,
                code_sha=args.code_sha,
            ),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
