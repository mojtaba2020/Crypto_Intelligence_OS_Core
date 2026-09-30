#!/usr/bin/env python3
"""Immutable chronological train/validation/locked-test boundaries."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Split:
    train_end: int
    validation_end: int
    locked_test_end: int

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


def chronological_split(
    n_bars: int,
    minimum_history_bars: int,
    horizon_bars: int,
    validation_fraction: float = 0.20,
    locked_fraction: float = 0.20,
) -> Split:
    """Return non-overlapping boundaries; end indices are exclusive."""
    if n_bars <= 0 or minimum_history_bars <= 0 or horizon_bars <= 0:
        raise ValueError("Split parameters must be positive")
    if not 0.0 < validation_fraction < 1.0 or not 0.0 < locked_fraction < 1.0:
        raise ValueError("Fractions must be strictly between zero and one")
    if validation_fraction + locked_fraction >= 1.0:
        raise ValueError("Validation plus locked fraction must leave training history")

    usable_end = n_bars - horizon_bars
    if usable_end <= minimum_history_bars:
        raise ValueError("Insufficient history after reserving forecast horizon")

    locked_size = max(1, int(usable_end * locked_fraction))
    validation_size = max(1, int(usable_end * validation_fraction))
    train_end = usable_end - validation_size - locked_size
    validation_end = train_end + validation_size
    if train_end < minimum_history_bars:
        raise ValueError("Insufficient training history after locking evaluation sets")
    return Split(
        train_end=train_end,
        validation_end=validation_end,
        locked_test_end=usable_end,
    )

def minimum_total_bars_required(
    minimum_history_bars: int,
    horizon_bars: int,
    validation_fraction: float = 0.20,
    locked_fraction: float = 0.20,
) -> int:
    """Return the smallest series length that satisfies the declared split contract."""
    if minimum_history_bars <= 0 or horizon_bars <= 0:
        raise ValueError("Split parameters must be positive")
    n_bars = minimum_history_bars + horizon_bars + 2
    while True:
        try:
            chronological_split(
                n_bars,
                minimum_history_bars,
                horizon_bars,
                validation_fraction,
                locked_fraction,
            )
            return n_bars
        except ValueError:
            n_bars += 1


def origins_for_phase(split: Split, phase: str, step: int) -> list[int]:
    if step <= 0:
        raise ValueError("Step must be positive")
    if phase == "validation":
        start, end = split.train_end, split.validation_end
    elif phase == "locked_test":
        start, end = split.validation_end, split.locked_test_end
    else:
        raise ValueError(f"Unknown phase: {phase}")
    return list(range(start, end, step))
