from __future__ import annotations

import pytest
from scripts.multitimeframe_prospective_audit_v1 import (
    ProspectiveSpec,
    audit_observations,
)


def _spec() -> ProspectiveSpec:
    return ProspectiveSpec(
        horizon_label="1d",
        candidate="ridge",
        family="daily",
        horizon_bars=1,
        frozen_git_sha="210f6321f5a191fee9c01b07e283c566a013f497",
        data_identity="synthetic-contract-test",
        freeze_timestamp=1_800_000_000,
    )


def test_fingerprint_is_deterministic() -> None:
    assert _spec().fingerprint() == _spec().fingerprint()


def test_only_post_freeze_observations_are_accepted() -> None:
    with pytest.raises(ValueError, match="freeze"):
        audit_observations(
            _spec(),
            [
                {
                    "issued_timestamp": 1_800_000_000,
                    "matured_timestamp": 1_800_086_400,
                    "prediction": 101.0,
                    "baseline": 100.0,
                    "actual": 102.0,
                }
            ],
        )


def test_audit_reports_evidence_but_never_auto_promotes() -> None:
    rows = []
    for i in range(8):
        issued = 1_800_000_001 + i * 86_400
        rows.append(
            {
                "issued_timestamp": issued,
                "matured_timestamp": issued + 86_400,
                "prediction": 101.5 + i,
                "baseline": 100.0 + i,
                "actual": 102.0 + i,
            }
        )
    report = audit_observations(_spec(), rows)
    assert report["samples"] == 8
    assert report["enough_samples"] is True
    assert report["mean_improvement"] > 0.0
    assert report["prospective_confirmation"] is True
    assert report["production_promotion"] is False


def test_empty_observations_fail_closed() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        audit_observations(_spec(), [])
