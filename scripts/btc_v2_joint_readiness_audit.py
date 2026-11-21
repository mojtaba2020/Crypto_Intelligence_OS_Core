"""Label-blind BTC technical/fundamental matched-origin readiness, Stage 6 E2.

Technical inputs are CLOSED BUCKET METADATA ONLY, not prices or future labels.
Source availability times and origin calendars still require independent audit.
No training, model promotion, inferred historical source witness, or trading.
"""

from __future__ import annotations

import argparse
import json
from bisect import bisect_right
from datetime import datetime, timedelta
from pathlib import Path

from scripts.btc_v2_fundamental_coverage_audit import HORIZONS, audit_coverage
from scripts.btc_v2_fundamental_features import summarize_fundamentals
from scripts.btc_v2_news_evidence import EvidenceError, utc

# Mirror the V1 13-horizon lab's explicitly predeclared MINIMUM history,
# not a post-outcome fitted hyperparameter.
HORIZON_SOURCE = {
    **{h: "1h" for h in ("1h", "2h", "3h", "4h", "12h")},
    **{h: "1d" for h in ("1d", "2d", "3d")},
    **{h: "1w" for h in ("1w", "2w", "3w")},
    **{h: "1mo" for h in ("1mo", "3mo")},
}
MIN_BARS = {"1h": 2200, "1d": 1460, "1w": 260, "1mo": 120}
MAX_BUCKETS = 200_000


def next_close(at: datetime, family: str) -> datetime:
    if family == "1mo":
        return (
            at.replace(year=at.year + 1, month=1)
            if at.month == 12
            else at.replace(month=at.month + 1)
        )
    return (
        at + {"1h": timedelta(hours=1), "1d": timedelta(days=1), "1w": timedelta(weeks=1)}[family]
    )


def _load_buckets(raw: dict) -> dict[str, tuple[list[datetime], list[int]]]:
    if not isinstance(raw, dict) or set(raw) != set(MIN_BARS):
        raise EvidenceError("technical buckets must have exact 1h/1d/1w/1mo keys")
    if sum(len(v) if isinstance(v, list) else MAX_BUCKETS + 1 for v in raw.values()) > MAX_BUCKETS:
        raise EvidenceError("unbounded technical bucket inventory")
    parsed: dict[str, tuple[list[datetime], list[int]]] = {}
    for family in MIN_BARS:
        closings: list[datetime] = []
        streak: list[int] = []
        for row in raw[family]:
            if not isinstance(row, dict) or set(row) != {"close_at_utc", "is_complete"}:
                raise EvidenceError("technical bucket must be label-free metadata")
            if type(row["is_complete"]) is not bool:
                raise EvidenceError("complete flag must be bool")
            dt = utc(row["close_at_utc"])
            if dt.minute or dt.second or dt.microsecond:
                raise EvidenceError("noncanonical technical closing timestamp")
            if family == "1d" and dt.hour != 0:
                raise EvidenceError("daily close must use UTC midnight")
            if family == "1w" and (dt.hour != 0 or dt.weekday() != 0):
                raise EvidenceError("weekly close must use Monday UTC midnight")
            if family == "1mo" and (dt.hour != 0 or dt.day != 1):
                raise EvidenceError("monthly close must use first of month UTC midnight")
            if closings and dt <= closings[-1]:
                raise EvidenceError("duplicate or nonincreasing source close")
            continuous = bool(closings and next_close(closings[-1], family) == dt)
            prior = streak[-1] if continuous else 0
            closings.append(dt)
            streak.append(prior + 1 if row["is_complete"] else 0)
        parsed[family] = closings, streak
    return parsed


def audit_joint_readiness(payload: dict) -> dict:
    if not isinstance(payload, dict) or set(payload) != {
        "origins",
        "observations",
        "technical_buckets",
    }:
        raise EvidenceError("joint input requires origins, observations and technical_buckets only")
    if set(HORIZON_SOURCE) != HORIZONS:
        raise EvidenceError("joint audit diverges from 13-horizon charter")
    fundamental = audit_coverage(
        {"origins": payload["origins"], "observations": payload["observations"]}
    )
    inventory = _load_buckets(payload["technical_buckets"])
    technical_ready = {h: 0 for h in sorted(HORIZONS)}
    fundamental_any = {h: 0 for h in sorted(HORIZONS)}
    joint_any = {h: 0 for h in sorted(HORIZONS)}
    short_history = {h: 0 for h in sorted(HORIZONS)}
    stale_technical = {h: 0 for h in sorted(HORIZONS)}
    for origin in payload["origins"]:
        horizon = origin["horizon"]
        cutoff = utc(origin["cutoff_utc"])
        family = HORIZON_SOURCE[horizon]
        closings, streak = inventory[family]
        index = bisect_right(closings, cutoff) - 1
        if index < 0 or cutoff >= next_close(closings[index], family):
            stale_technical[horizon] += 1
            ready = False
        else:
            ready = streak[index] >= MIN_BARS[family]
            if not ready:
                short_history[horizon] += 1
        if ready:
            technical_ready[horizon] += 1
        any_fundamental = (
            summarize_fundamentals(payload["observations"], origin["cutoff_utc"])[
                "available_metric_count"
            ]
            > 0
        )
        if any_fundamental:
            fundamental_any[horizon] += 1
        if ready and any_fundamental:
            joint_any[horizon] += 1
    return {
        "status": "STAGE6_UNATTESTED_LABEL_BLIND_JOINT_FEASIBILITY_ONLY",
        "technical_family_minimum_complete_consecutive_bars": MIN_BARS,
        "technical_bucket_count": {family: len(x[0]) for family, x in inventory.items()},
        "by_horizon": {
            h: {
                "origins": fundamental["horizons"][h]["scheduled_origins"],
                "technical_history_count_ready": technical_ready[h],
                "fundamental_any_count": fundamental_any[h],
                "matched_technical_and_any_fundamental_count": joint_any[h],
                "technical_short_or_gapped_history_count": short_history[h],
                "technical_stale_or_unavailable_count": stale_technical[h],
                "fundamental_coverage": fundamental["horizons"][h],
            }
            for h in sorted(HORIZONS)
        },
        "first_seen_source_independently_attested": False,
        "locked_outcomes_or_future_labels_used": False,
        "eligible_for_training_or_promotion": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error("input and output must differ")
    if args.input.stat().st_size > 12_000_000:
        parser.error("input too large")
    result = audit_joint_readiness(json.loads(args.input.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temp = args.output.with_name(args.output.name + ".tmp")
    try:
        temp.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temp.replace(args.output)
    finally:
        temp.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
