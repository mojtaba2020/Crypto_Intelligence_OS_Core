"""Stage-6 label-blind availability audit for the 13 BTC forecast horizons.

Offline metadata-only study. No market downloads, training, model ranking,
access to locked outcomes, historical first-seen attestation or paid services.
The audit validates *claimed* source timestamps, not their external truth.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from scripts.btc_v2_fundamental_features import (
    MAX_EVENTS,
    METRICS,
    summarize_fundamentals,
)
from scripts.btc_v2_news_evidence import EvidenceError, utc

HORIZONS = frozenset(
    (
        "1h",
        "2h",
        "3h",
        "4h",
        "12h",
        "1d",
        "2d",
        "3d",
        "1w",
        "2w",
        "3w",
        "1mo",
        "3mo",
    )
)
MAX_ORIGINS = 500
MAX_PAIR_CHECKS = 200_000


def audit_coverage(payload: dict) -> dict:
    """Count cutoff-eligible observed metrics without reading future labels.

    Inputs contain only issue cutoffs and metadata observations. Reject
    unknown fields rather than accidentally accepting target outcomes.
    A 'first_seen_at' string is an unauthenticated assertion until an
    external source custodian verifies the original collection receipt.
    """
    if not isinstance(payload, dict) or set(payload) != {"origins", "observations"}:
        raise EvidenceError("coverage input must contain only origins and observations")
    origins = payload["origins"]
    observations = payload["observations"]
    if (
        not isinstance(origins, list)
        or not 1 <= len(origins) <= MAX_ORIGINS
        or not isinstance(observations, list)
        or len(observations) > MAX_EVENTS
        or len(origins) * len(observations) > MAX_PAIR_CHECKS
    ):
        raise EvidenceError("coverage audit input exceeds bounded limits")

    seen_keys: set[tuple[str, str]] = set()
    previous_by_horizon: dict[str, datetime] = {}
    totals = {h: 0 for h in sorted(HORIZONS)}
    count_any = {h: 0 for h in sorted(HORIZONS)}
    counts = {h: {m: 0 for m in sorted(METRICS)} for h in sorted(HORIZONS)}
    groups = sorted(set(METRICS.values()))
    group_counts = {h: {g: 0 for g in groups} for h in sorted(HORIZONS)}
    rejected_late = {h: 0 for h in sorted(HORIZONS)}
    rejected_stale = {h: 0 for h in sorted(HORIZONS)}

    for origin in origins:
        if not isinstance(origin, dict) or set(origin) != {"horizon", "cutoff_utc"}:
            raise EvidenceError("origin must contain only horizon and cutoff_utc")
        horizon = origin["horizon"]
        if not isinstance(horizon, str) or horizon not in HORIZONS:
            raise EvidenceError("unknown horizon")
        at = utc(origin["cutoff_utc"])
        key = (horizon, at.isoformat())
        if key in seen_keys:
            raise EvidenceError("duplicate forecast origin")
        seen_keys.add(key)
        previous = previous_by_horizon.get(horizon)
        if previous is not None and at <= previous:
            raise EvidenceError("forecast origins must increase within each horizon")
        previous_by_horizon[horizon] = at

        snapshot = summarize_fundamentals(observations, at.isoformat())
        totals[horizon] += 1
        rejected_late[horizon] += snapshot["excluded_late"]
        rejected_stale[horizon] += snapshot["excluded_stale"]
        if snapshot["available_metric_count"] > 0:
            count_any[horizon] += 1
        present_groups: set[str] = set()
        for metric, present in snapshot["has_value"].items():
            if present:
                counts[horizon][metric] += 1
                present_groups.add(METRICS[metric])
        for group in present_groups:
            group_counts[horizon][group] += 1

    by_horizon = {
        horizon: {
            "scheduled_origins": totals[horizon],
            "origins_with_any_metric": count_any[horizon],
            "metric_coverage_counts": counts[horizon],
            "group_any_coverage_counts": group_counts[horizon],
            "late_observations_excluded": rejected_late[horizon],
            "stale_observations_excluded": rejected_stale[horizon],
            "covered_origin_fraction": (
                count_any[horizon] / totals[horizon] if totals[horizon] else None
            ),
        }
        for horizon in sorted(HORIZONS)
    }
    return {
        "status": "STAGE6_LABEL_BLIND_UNATTESTED_COVERAGE_ONLY",
        "horizons": by_horizon,
        "registered_metrics": len(METRICS),
        "input_origin_count": len(origins),
        "input_observation_count": len(observations),
        "source_first_seen_independently_verified": False,
        "labels_or_future_outcomes_used": False,
        "power_or_predictive_edge_established": False,
        "training_or_freeze_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error("input and output must be different")
    if args.input.stat().st_size > 5_000_000:
        parser.error("input too large")
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    result = audit_coverage(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    candidate = args.output.with_name(args.output.name + ".tmp")
    try:
        candidate.write_text(
            json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        candidate.replace(args.output)
    finally:
        candidate.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
