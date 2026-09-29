#!/usr/bin/env python3
"""Prospective evidence audit: freeze before observations, score after maturity."""

from __future__ import annotations

import hashlib
import json
import statistics
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ProspectiveSpec:
    horizon_label: str
    candidate: str
    family: str
    horizon_bars: int
    frozen_git_sha: str
    data_identity: str
    freeze_timestamp: int

    def canonical_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))

    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()


def validate_spec(spec: ProspectiveSpec) -> None:
    if not spec.horizon_label or not spec.candidate or not spec.family:
        raise ValueError("Prospective identity fields cannot be empty")
    if spec.horizon_bars <= 0 or spec.freeze_timestamp <= 0:
        raise ValueError("Prospective horizon and freeze timestamp must be positive")
    if len(spec.frozen_git_sha) < 7 or not spec.data_identity:
        raise ValueError("Prospective provenance is incomplete")


def audit_observations(
    spec: ProspectiveSpec,
    observations: list[dict[str, float]],
    *,
    minimum_samples: int = 8,
) -> dict[str, object]:
    """Audit only forecasts issued strictly after the immutable freeze point."""
    validate_spec(spec)
    if minimum_samples < 2:
        raise ValueError("minimum_samples must be at least 2")
    accepted: list[dict[str, float]] = []
    for row in observations:
        issued = int(row["issued_timestamp"])
        matured = int(row["matured_timestamp"])
        if issued <= spec.freeze_timestamp:
            raise ValueError("Observation predates or equals prospective freeze")
        if matured <= issued:
            raise ValueError("Observation maturity must follow issuance")
        actual = float(row["actual"])
        prediction = float(row["prediction"])
        baseline = float(row["baseline"])
        if actual <= 0 or prediction <= 0 or baseline <= 0:
            raise ValueError("Prices must be positive")
        accepted.append(row)
    if not accepted:
        raise ValueError("Prospective observations cannot be empty")

    challenger_losses = [
        abs(float(row["prediction"]) - float(row["actual"])) / float(row["actual"])
        for row in accepted
    ]
    baseline_losses = [
        abs(float(row["baseline"]) - float(row["actual"])) / float(row["actual"])
        for row in accepted
    ]
    improvements = [
        baseline - challenger
        for baseline, challenger in zip(baseline_losses, challenger_losses, strict=True)
    ]
    enough = len(accepted) >= minimum_samples
    return {
        "spec_fingerprint": spec.fingerprint(),
        "samples": len(accepted),
        "minimum_samples": minimum_samples,
        "enough_samples": enough,
        "challenger_mape": statistics.mean(challenger_losses),
        "persistence_mape": statistics.mean(baseline_losses),
        "mean_improvement": statistics.mean(improvements),
        "prospective_confirmation": enough and statistics.mean(improvements) > 0.0,
        "production_promotion": False,
    }
