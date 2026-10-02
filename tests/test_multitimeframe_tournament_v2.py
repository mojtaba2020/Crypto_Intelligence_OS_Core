from __future__ import annotations

from scripts import multitimeframe_tournament_v2 as tournament_v2
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


def test_v2_ridge_fit_does_not_recurse_into_mutated_v1_state() -> None:
    x = [[float(i), float(i % 3)] for i in range(1, 25)]
    y = [0.001 * float(i) for i in range(1, 25)]
    predictor = tournament_v2._fit_candidate("ridge", x, y)
    prediction = predictor([25.0, 1.0])
    assert isinstance(float(prediction), float)
