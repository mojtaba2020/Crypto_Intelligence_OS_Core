from __future__ import annotations

import pytest
from scripts.multitimeframe_exchange_replication_v1 import (
    ReplicationSpec,
    replication_decision,
)


def _spec() -> ReplicationSpec:
    return ReplicationSpec(
        horizon_label="1d",
        family="daily",
        candidate="ridge",
        discovery_exchange="bitstamp",
        replication_exchange="bitfinex",
        frozen_git_sha="4f327d7407236285f7050c8a176a08487685c986",
        discovery_data_identity="bitstamp-locked-v1",
        replication_data_identity="bitfinex-independent-v1",
    )


def test_same_exchange_fails_closed() -> None:
    spec = ReplicationSpec(**{**_spec().__dict__, "replication_exchange": "bitstamp"})
    with pytest.raises(ValueError, match="independent exchange"):
        replication_decision(
            spec, prospective_confirmed=True, holm_reject=True, ci95_low=0.1, mean_improvement=0.2
        )


def test_all_evidence_gates_are_required() -> None:
    report = replication_decision(
        _spec(),
        prospective_confirmed=True,
        holm_reject=True,
        ci95_low=0.01,
        mean_improvement=0.02,
    )
    assert report["replication_status"] == "REPLICATED_RESEARCH_EDGE"
    assert report["model_registry_eligible"] is True
    assert report["production_promotion"] is False


@pytest.mark.parametrize(
    ("prospective", "holm", "ci_low", "improvement"),
    [
        (False, True, 0.01, 0.02),
        (True, False, 0.01, 0.02),
        (True, True, -0.01, 0.02),
        (True, True, 0.01, -0.02),
    ],
)
def test_any_missing_gate_blocks_replication(
    prospective: bool, holm: bool, ci_low: float, improvement: float
) -> None:
    report = replication_decision(
        _spec(),
        prospective_confirmed=prospective,
        holm_reject=holm,
        ci95_low=ci_low,
        mean_improvement=improvement,
    )
    assert report["replication_status"] == "NOT_REPLICATED"
    assert report["model_registry_eligible"] is False
