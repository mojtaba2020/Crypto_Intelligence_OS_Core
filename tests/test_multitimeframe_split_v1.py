from __future__ import annotations

import pytest

from scripts.multitimeframe_split_v1 import chronological_split, origins_for_phase


def test_validation_and_locked_test_are_disjoint_and_ordered() -> None:
    split = chronological_split(2000, 365, 3)
    validation = origins_for_phase(split, "validation", 7)
    locked = origins_for_phase(split, "locked_test", 7)
    assert validation
    assert locked
    assert max(validation) < min(locked)
    assert split.train_end < split.validation_end < split.locked_test_end <= 1997


def test_horizon_tail_is_never_an_evaluation_origin() -> None:
    split = chronological_split(1000, 365, 3)
    locked = origins_for_phase(split, "locked_test", 1)
    assert max(locked) + 3 < 1000


def test_locked_boundaries_do_not_depend_on_model_or_features() -> None:
    first = chronological_split(2000, 365, 3)
    second = chronological_split(2000, 365, 3)
    assert first == second


@pytest.mark.parametrize("phase", ["train", "future", ""])
def test_unknown_phase_fails_closed(phase: str) -> None:
    split = chronological_split(2000, 365, 3)
    with pytest.raises(ValueError, match="Unknown phase"):
        origins_for_phase(split, phase, 7)


def test_insufficient_history_fails_closed() -> None:
    with pytest.raises(ValueError, match="Insufficient"):
        chronological_split(400, 365, 3)
