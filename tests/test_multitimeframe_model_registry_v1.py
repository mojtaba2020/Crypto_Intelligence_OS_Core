from __future__ import annotations

import pytest
from scripts.multitimeframe_model_registry_v1 import RegistryEvidence, register


def _evidence(**overrides: object) -> RegistryEvidence:
    values: dict[str, object] = {
        "horizon_label": "1d",
        "family": "daily",
        "candidate": "ridge",
        "frozen_git_sha": "6a2d73b05b84972491b2d5a7aa4e38843ee580ee",
        "judge_fingerprint": "judge-0123456789abcdef",
        "prospective_fingerprint": "prospective-0123456789abcdef",
        "replication_fingerprint": "replication-0123456789abcdef",
        "locked_oos_passed": True,
        "prospective_confirmed": True,
        "independent_replication_confirmed": True,
    }
    values.update(overrides)
    return RegistryEvidence(**values)  # type: ignore[arg-type]


def test_complete_evidence_is_registry_eligible_but_not_live() -> None:
    row = register(_evidence())
    assert row["status"] == "EVIDENCE_VERIFIED"
    assert row["registry_eligible"] is True
    assert row["champion"] == "persistence"
    assert row["live_authorized"] is False
    assert row["automatic_promotion"] is False


@pytest.mark.parametrize(
    "field",
    ["locked_oos_passed", "prospective_confirmed", "independent_replication_confirmed"],
)
def test_missing_evidence_gate_fails_closed(field: str) -> None:
    row = register(_evidence(**{field: False}))
    assert row["status"] == "EVIDENCE_INCOMPLETE"
    assert row["registry_eligible"] is False
    assert row["champion"] == "persistence"


def test_incomplete_provenance_fails_closed() -> None:
    with pytest.raises(ValueError, match="fingerprints"):
        register(_evidence(replication_fingerprint="short"))


def test_registry_fingerprint_is_deterministic() -> None:
    assert register(_evidence())["registry_fingerprint"] == register(_evidence())[
        "registry_fingerprint"
    ]
