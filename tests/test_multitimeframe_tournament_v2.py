from __future__ import annotations

from scripts.multitimeframe_tournament_v1 import CANDIDATES as V1_CANDIDATES
from scripts.multitimeframe_tournament_v2 import CANDIDATES as V2_CANDIDATES


def test_v1_evidence_candidate_set_remains_frozen() -> None:
    assert V1_CANDIDATES == ("ridge", "extra_trees", "boosting")


def test_v2_classical_lane_is_separate_and_deterministic() -> None:
    assert V2_CANDIDATES == (
        "ridge",
        "elastic_net",
        "extra_trees",
        "random_forest",
        "hist_gradient_boosting",
        "boosting",
    )
    assert len(V2_CANDIDATES) == len(set(V2_CANDIDATES))
