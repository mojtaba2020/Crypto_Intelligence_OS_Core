#!/usr/bin/env python3
"""Independent-exchange replication contract for multi-timeframe evidence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

ALLOWED_EXCHANGES = ("bitstamp", "bitfinex")


@dataclass(frozen=True)
class ReplicationSpec:
    horizon_label: str
    family: str
    candidate: str
    discovery_exchange: str
    replication_exchange: str
    frozen_git_sha: str
    discovery_data_identity: str
    replication_data_identity: str

    def canonical_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))

    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()


def validate_replication_spec(spec: ReplicationSpec) -> None:
    if spec.discovery_exchange not in ALLOWED_EXCHANGES:
        raise ValueError("Discovery exchange is not declared")
    if spec.replication_exchange not in ALLOWED_EXCHANGES:
        raise ValueError("Replication exchange is not declared")
    if spec.discovery_exchange == spec.replication_exchange:
        raise ValueError("Replication must use an independent exchange")
    if spec.discovery_data_identity == spec.replication_data_identity:
        raise ValueError("Replication data identity must be independent")
    if len(spec.frozen_git_sha) < 7:
        raise ValueError("Frozen git provenance is incomplete")
    if not spec.horizon_label or not spec.family or not spec.candidate:
        raise ValueError("Replication identity fields cannot be empty")


def replication_decision(
    spec: ReplicationSpec,
    *,
    prospective_confirmed: bool,
    holm_reject: bool,
    ci95_low: float,
    mean_improvement: float,
) -> dict[str, object]:
    """Apply the locked replication gate without automatic production promotion."""
    validate_replication_spec(spec)
    replicated = prospective_confirmed and holm_reject and mean_improvement > 0.0 and ci95_low > 0.0
    return {
        "spec_fingerprint": spec.fingerprint(),
        "discovery_exchange": spec.discovery_exchange,
        "replication_exchange": spec.replication_exchange,
        "prospective_confirmed": prospective_confirmed,
        "holm_reject": holm_reject,
        "ci95_low": ci95_low,
        "mean_improvement": mean_improvement,
        "replication_status": ("REPLICATED_RESEARCH_EDGE" if replicated else "NOT_REPLICATED"),
        "model_registry_eligible": replicated,
        "production_promotion": False,
    }
