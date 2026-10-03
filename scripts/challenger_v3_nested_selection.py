"""Fail-closed nested selection utilities for Challenger V3 development research.

This module separates candidate selection from diagnostic evaluation inside the
existing development/validation region. It never accesses locked OOS data.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


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


def select_candidate(
    origin_records: Sequence[Mapping[str, object]],
    candidates: Sequence[str],
    policy: NestedSelectionPolicy = NestedSelectionPolicy(),
) -> tuple[str, int]:
    """Select only on the earlier origin subset using mean absolute percentage loss."""
    cut = policy.boundary(len(origin_records))
    if not candidates:
        raise ValueError("candidate list must not be empty")
    rank = {name: i for i, name in enumerate(candidates)}
    means: dict[str, float] = {}
    for name in candidates:
        losses = [float(r["candidate_errors"][name]) for r in origin_records[:cut]]
        means[name] = sum(losses) / len(losses)
    winner = min(candidates, key=lambda n: (means[n], rank[n]))
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
            float(record["persistence_error"])
            - float(record["candidate_errors"][candidate])
        )
    return out


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
