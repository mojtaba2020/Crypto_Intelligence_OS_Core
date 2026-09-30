#!/usr/bin/env python3
"""Fail-closed evidence registry for multi-timeframe model candidates."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class RegistryEvidence:
    horizon_label: str
    family: str
    candidate: str
    frozen_git_sha: str
    judge_fingerprint: str
    prospective_fingerprint: str
    replication_fingerprint: str
    locked_oos_passed: bool
    prospective_confirmed: bool
    independent_replication_confirmed: bool

    def canonical_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))

    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()


def register(evidence: RegistryEvidence) -> dict[str, object]:
    """Register evidence only; never silently promote a model to production."""
    identity = (evidence.horizon_label, evidence.family, evidence.candidate)
    if any(not value for value in identity):
        raise ValueError("Registry identity fields cannot be empty")
    if len(evidence.frozen_git_sha) < 7:
        raise ValueError("Frozen git provenance is incomplete")
    fingerprints = (
        evidence.judge_fingerprint,
        evidence.prospective_fingerprint,
        evidence.replication_fingerprint,
    )
    if any(len(value) < 16 for value in fingerprints):
        raise ValueError("Evidence fingerprints are incomplete")
    eligible = (
        evidence.locked_oos_passed
        and evidence.prospective_confirmed
        and evidence.independent_replication_confirmed
    )
    return {
        "registry_fingerprint": evidence.fingerprint(),
        "horizon_label": evidence.horizon_label,
        "family": evidence.family,
        "candidate": evidence.candidate,
        "status": "EVIDENCE_VERIFIED" if eligible else "EVIDENCE_INCOMPLETE",
        "registry_eligible": eligible,
        "champion": "persistence",
        "challenger": evidence.candidate,
        "live_authorized": False,
        "automatic_promotion": False,
    }
