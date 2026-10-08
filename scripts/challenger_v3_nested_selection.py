"""Fail-closed nested selection utilities for Challenger V3 development research.

This module separates candidate selection from diagnostic evaluation inside the
existing development/validation region. It never accesses locked OOS data.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class NestedSelectionPolicy:
    selection_fraction: float = 0.60
    minimum_selection_origins: int = 20
    minimum_diagnostic_origins: int = 15

    def boundary(self, origin_count: int) -> int:
        if origin_count < self.minimum_selection_origins + self.minimum_diagnostic_origins:
            raise ValueError("insufficient origins for nested selection diagnostics")
        cut = max(self.minimum_selection_origins, int(origin_count * self.selection_fraction))
        cut = min(cut, origin_count - self.minimum_diagnostic_origins)
        return cut


DEFAULT_NESTED_SELECTION_POLICY = NestedSelectionPolicy()


def select_candidate(
    origin_records: Sequence[Mapping[str, object]],
    candidates: Sequence[str],
    policy: NestedSelectionPolicy = DEFAULT_NESTED_SELECTION_POLICY,
) -> tuple[str, int]:
    """Select only on the earlier origin subset using mean absolute percentage loss."""
    cut = policy.boundary(len(origin_records))
    if not candidates:
        raise ValueError("candidate list must not be empty")
    canonical_candidates = tuple(sorted(set(candidates)))
    if len(canonical_candidates) != len(candidates):
        raise ValueError("candidate names must be unique")
    rank = {name: i for i, name in enumerate(canonical_candidates)}
    means: dict[str, float] = {}
    for name in candidates:
        losses = [float(r["candidate_errors"][name]) for r in origin_records[:cut]]
        means[name] = sum(losses) / len(losses)
    winner = min(canonical_candidates, key=lambda n: (means[n], rank[n]))
    return winner, cut


def heldout_paired_differences(
    origin_records: Sequence[Mapping[str, object]],
    candidate: str,
    cut: int,
) -> list[float]:
    """Return persistence minus candidate loss on later, untouched diagnostic origins."""
    if cut <= 0 or cut >= len(origin_records):
        raise ValueError("invalid nested diagnostic boundary")
    out = []
    for record in origin_records[cut:]:
        out.append(
            float(record["persistence_error"]) - float(record["candidate_errors"][candidate])
        )
    return out


def purged_diagnostic_records(
    origin_records: Sequence[Mapping[str, object]],
    cut: int,
    *,
    horizon_bars: int,
    evaluation_step_bars: int,
) -> tuple[list[Mapping[str, object]], int]:
    """Return diagnostic records after purging target overlap at the split boundary.

    The last selection forecast matures ``horizon_bars`` after its origin.  Origins
    are ``evaluation_step_bars`` apart, so only the intervening origins whose
    targets would overlap the selection target are removed.
    """
    if cut <= 0 or cut >= len(origin_records):
        raise ValueError("invalid nested diagnostic boundary")
    if horizon_bars <= 0 or evaluation_step_bars <= 0:
        raise ValueError("horizon and evaluation step must be positive")
    fallback_purged = max(0, math.ceil(horizon_bars / evaluation_step_bars) - 1)

    timestamps_present = [record.get("origin_timestamp") is not None for record in origin_records]
    target_timestamp = origin_records[cut - 1].get("target_timestamp")
    if any(timestamps_present) or target_timestamp is not None:
        if not all(timestamps_present) or target_timestamp is None:
            raise ValueError("complete timestamp metadata is required for exact target-maturity purge")
        maturity = float(target_timestamp)
        start = cut
        while start < len(origin_records):
            origin_timestamp = float(origin_records[start]["origin_timestamp"])
            if origin_timestamp >= maturity:
                break
            start += 1
        purged = start - cut
    else:
        # Legacy isolated utility callers may lack timestamps. Production V3
        # statistical evidence is validated separately and must provide them.
        purged = fallback_purged
        start = cut + purged

    if start >= len(origin_records):
        raise ValueError("target-maturity purge leaves no diagnostic origins")
    return list(origin_records[start:]), purged


def evidence_manifest(candidate: str, cut: int, origin_count: int) -> dict[str, object]:
    return {
        "status": "CHALLENGER_V3_NESTED_DEVELOPMENT_DIAGNOSTIC_ONLY",
        "selected_candidate": candidate,
        "selection_origin_count": cut,
        "diagnostic_origin_count": origin_count - cut,
        "fresh_locked_oos_access": False,
        "v2_locked_oos_used_for_tuning": False,
        "confirmatory": False,
        "production_eligible": False,
    }
