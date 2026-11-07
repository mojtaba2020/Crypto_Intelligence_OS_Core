"""Fixed one-shot historical test of a BTC volume-confirmed challenger.

This deliberately repeats an ALREADY-EXPOSED October 2026 price interval.
It can falsify a hypothesis, but cannot become independent confirmatory alpha.
All first-observed times are explicitly hypothetical, not real vintage proofs.
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

from scripts.alpha_4h_training_bridge import FiveMinuteTarget
from scripts.alpha_coinbase_historical_replay import (
    API,
    ASSUMED_AFTER_CLOSE,
    USER_AGENT,
    fetch_candles,
    iso,
)
from scripts.alpha_volume_confirmation import (
    HourlyVolumeBar,
    make_volume_training_row,
    walk_forward_volume_candidate,
)

FIXED_RIDGE = 100.0
EXPECTED_FIRST_RECEIPT_IS_HYPOTHETICAL = True


def fetch_public_hourly_close_volume(
    start: datetime, end: datetime
) -> dict[datetime, tuple[float, float]]:
    """Download historical 1h BTC-USD close and BTC base-asset traded volume.

    Coinbase Exchange REST returns [time, low, high, open, close, volume].
    An original historical source-vintage receipt is NOT provided by this API.
    """
    if start.utcoffset() != timedelta(0) or end.utcoffset() != timedelta(0):
        raise ValueError("UTC-aware request bounds required")
    if not start < end or end - start > timedelta(days=40):
        raise ValueError("allowed history download is at most 40 days")
    cursor = start
    found: dict[datetime, tuple[float, float]] = {}
    while cursor < end:
        stop = min(end, cursor + timedelta(hours=250))
        query = urllib.parse.urlencode(
            {"start": iso(cursor), "end": iso(stop), "granularity": 3600}
        )
        request = urllib.request.Request(  # noqa: S310 -- fixed public Coinbase HTTPS URL
            f"{API}?{query}",
            headers={"User-Agent": USER_AGENT},
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
            raise ValueError("non-list Coinbase hourly response")
        for record in data:
            if not isinstance(record, list) or len(record) < 6:
                raise ValueError("malformed OHLCV: volume column unavailable")
            stamp = datetime.fromtimestamp(int(record[0]), UTC)
            if not cursor <= stamp < stop:
                continue
            close = float(record[4])
            volume_btc = float(record[5])
            if (
                int(stamp.timestamp()) % 3600 != 0
                or not math.isfinite(close)
                or not math.isfinite(volume_btc)
                or close <= 0
                or volume_btc <= 0
            ):
                raise ValueError("invalid hourly BTC close or base volume")
            value = (close, volume_btc)
            if stamp in found and found[stamp] != value:
                raise ValueError("conflicting duplicate hourly OHLCV revisions")
            found[stamp] = value
        cursor = stop
        time.sleep(0.15)
    return found


def _hash_ohlcv(rows: dict[datetime, tuple[float, float]]) -> str:
    canonical = json.dumps(
        [[iso(stamp), close, volume] for stamp, (close, volume) in sorted(rows.items())],
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def run_volume_historical_replay(
    hourly: dict[datetime, tuple[float, float]],
    targets_5min: dict[datetime, float],
    *,
    start: datetime,
    end: datetime,
) -> dict[str, Any]:
    """Predeclared fixed-parameter development replay vs independent controls."""
    if start.utcoffset() != timedelta(0) or end.utcoffset() != timedelta(0):
        raise ValueError("UTC-aware study boundaries required")
    if (
        any((start.hour, start.minute, start.second, start.microsecond))
        or any((end.hour, end.minute, end.second, end.microsecond))
        or not timedelta(days=7) <= end - start <= timedelta(days=38)
    ):
        raise ValueError("require 7..38 complete UTC days")
    rejected = {"missing_1h_ohlcv": 0, "missing_5min_target": 0}
    expected = int((end - start) / timedelta(hours=4))
    origin = start
    rows = []
    while origin < end:
        stamps = [origin - timedelta(hours=25 - i) for i in range(25)]
        if any(stamp not in hourly for stamp in stamps):
            rejected["missing_1h_ohlcv"] += 1
            origin += timedelta(hours=4)
            continue
        target_stamp = origin + timedelta(hours=4, minutes=10)
        if target_stamp not in targets_5min:
            rejected["missing_5min_target"] += 1
            origin += timedelta(hours=4)
            continue
        bars = [
            HourlyVolumeBar(
                bar_open_utc=stamp,
                close_usd=hourly[stamp][0],
                base_volume_btc=hourly[stamp][1],
                first_observed_at_utc=stamp + timedelta(hours=1) + ASSUMED_AFTER_CLOSE,
            )
            for stamp in stamps
        ]
        target = FiveMinuteTarget(
            bar_open_utc=target_stamp,
            close_usd=targets_5min[target_stamp],
            first_observed_at_utc=target_stamp + timedelta(minutes=5) + ASSUMED_AFTER_CLOSE,
        )
        rows.append(
            make_volume_training_row(
                bars,
                origin_utc=origin,
                issued_at_utc=origin + timedelta(minutes=10),
                target=target,
                fit_at_utc=end + timedelta(days=1),
            )
        )
        origin += timedelta(hours=4)
    if len(rows) < 34:
        raise ValueError("insufficient complete historical rows")
    audit = walk_forward_volume_candidate(rows, ridge=FIXED_RIDGE)
    if not audit.scored:
        raise ValueError("no evaluable forecast origin after training warmup")

    losses = {
        "volume_interaction_candidate": "candidate_abs_log_error",
        "price_plus_volume_additive": "additive_abs_log_error",
        "price_only_momentum": "momentum_abs_log_error",
        "persistence": "persistence_abs_log_error",
    }
    means = {
        name: math.fsum(getattr(item, key) for item in audit.scored) / len(audit.scored)
        for name, key in losses.items()
    }
    def relative_gain(baseline: str) -> float | None:
        baseline_loss = means[baseline]
        return (
            100.0 * (baseline_loss - means["volume_interaction_candidate"]) / baseline_loss
            if baseline_loss > 0 else None
        )

    directional = {}
    for name, field in (
        ("volume_interaction_candidate", "candidate_log_return"),
        ("price_plus_volume_additive", "additive_log_return"),
        ("price_only_momentum", "momentum_log_return"),
    ):
        nonflat = [
            (getattr(score, field), score.realized_log_return)
            for score in audit.scored
            if abs(getattr(score, field)) > 1e-12
            and score.realized_log_return != 0
        ]
        correct = sum((p > 0) == (actual > 0) for p, actual in nonflat)
        directional[name] = {
            "nonflat_scored": len(nonflat),
            "correct": correct,
            "conditional_accuracy_pct": 100.0 * correct / len(nonflat) if nonflat else None,
            "all_scored_denominator": len(audit.scored),
        }
    return {
        "status": "EXPOSED_HISTORICAL_EXPLORATION_NOT_ALPHA",
        "market": "Coinbase Exchange BTC-USD",
        "source_volume_unit": "BTC base-asset volume, not bid/ask order flow",
        "window_start_utc": iso(start),
        "window_end_exclusive_utc": iso(end),
        "scheduled_origins": expected,
        "complete_origins": len(rows),
        "missing_origins": expected - len(rows),
        "rejected_origin_reasons": rejected,
        "cold_start_origins": audit.cold_start_origins,
        "walk_forward_scored": len(audit.scored),
        "candidate_interaction_active": sum(item.interaction_active for item in audit.scored),
        "mean_absolute_log_price_error": means,
        "candidate_gain_vs_persistence_pct": relative_gain("persistence"),
        "candidate_gain_vs_price_only_pct": relative_gain("price_only_momentum"),
        "candidate_gain_vs_volume_additive_pct": relative_gain("price_plus_volume_additive"),
        "direction_secondary": directional,
        "fixed_ridge": FIXED_RIDGE,
        "hourly_ohlcv_candles": len(hourly),
        "five_minute_close_candles": len(targets_5min),
        "hourly_time_close_volume_sha256": _hash_ohlcv(hourly),
        "initial_source_vintage_proven": False,
        "original_forecasts_issued_on_these_dates": False,
        "hypothetical_source_receipt": "each bar close+1s, NOT a measured historical observation",
        "hypothetical_issue": "S+10min, NOT an actual historic issuance",
        "research_status": "NO_RUN_NO_FREEZE_NO_TRADE",
        "limitations": (
            "The same already-seen October window drove earlier project decisions; "
            "this is hypothesis exploration, not untouched OOS. No first-receipt "
            "provenance, no provider revisions guarantee, no preregistered statistical "
            "power or independence. No positive gain can be claimed as real alpha."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2026-10-01")
    parser.add_argument("--end", default="2026-10-29")
    parser.add_argument("--output", type=Path, default=Path("alpha_4h_volume_research.json"))
    args = parser.parse_args()
    start = datetime.fromisoformat(args.start).replace(tzinfo=UTC)
    end = datetime.fromisoformat(args.end).replace(tzinfo=UTC)
    hourly = fetch_public_hourly_close_volume(start - timedelta(hours=25), end)
    targets = fetch_candles(
        start + timedelta(hours=4, minutes=10), end + timedelta(minutes=15), granularity=300
    )
    report = run_volume_historical_replay(hourly, targets, start=start, end=end)
    report["retrieved_at_utc"] = iso(datetime.now(UTC))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
