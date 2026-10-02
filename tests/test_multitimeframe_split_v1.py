from __future__ import annotations

import pytest
from scripts.multitimeframe_split_v1 import (
    chronological_split,
    minimum_total_bars_required,
    origins_for_phase,
)


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


def test_calendar_grid_length_drives_identical_split_boundaries() -> None:
    """Missing-market buckets must stay represented instead of compressing evaluation time."""
    canonical_grid_bars = 2000
    first = chronological_split(canonical_grid_bars, 365, 3)
    second = chronological_split(canonical_grid_bars, 365, 3)
    assert first.as_dict() == second.as_dict()
    assert first.locked_test_end == canonical_grid_bars - 3


@pytest.mark.parametrize("horizon", [1, 3, 12, 96])
def test_reserved_horizon_never_enters_evaluation_grid(horizon: int) -> None:
    split = chronological_split(2200, 365, horizon)
    validation = origins_for_phase(split, "validation", 1)
    locked = origins_for_phase(split, "locked_test", 1)
    assert max(validation) < min(locked)
    assert max(locked) + horizon < 2200


def test_minimum_total_bars_required_is_exact_boundary() -> None:
    required = minimum_total_bars_required(120, 1)
    chronological_split(required, 120, 1)
    with pytest.raises(ValueError, match="Insufficient"):
        chronological_split(required - 1, 120, 1)
