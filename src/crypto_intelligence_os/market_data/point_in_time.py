"""Deterministic point-in-time filtering helpers."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from crypto_intelligence_os.core.time import ensure_utc

from .contracts import BarStatus, OHLCVBar


class PointInTimeViolation(ValueError):
    """Raised when a decision or replay would consume future information."""


def validate_decision_cutoff(*, data_cutoff_time: datetime, decision_time: datetime) -> None:
    """Reject a decision whose declared data cutoff is in the future."""
    cutoff = ensure_utc(data_cutoff_time)
    decision = ensure_utc(decision_time)
    if cutoff > decision:
        raise PointInTimeViolation("data_cutoff_time cannot be later than decision_time.")


def bars_available_as_of(
    bars: Iterable[OHLCVBar],
    cutoff: datetime,
    *,
    include_partial: bool = False,
) -> tuple[OHLCVBar, ...]:
    """Return bars market-available by ``cutoff``, ordered by open time.

    This view is appropriate for explicitly labeled historical reconstruction.  It does
    not prove the system itself had ingested the records by the cutoff.
    """
    normalized_cutoff = ensure_utc(cutoff)
    eligible = (
        bar
        for bar in bars
        if bar.available_at <= normalized_cutoff
        and (include_partial or bar.status is BarStatus.FINAL)
    )
    return tuple(sorted(eligible, key=lambda bar: (bar.open_time, bar.bar_id)))


def bars_known_by_system_as_of(
    bars: Iterable[OHLCVBar],
    cutoff: datetime,
    *,
    include_partial: bool = False,
) -> tuple[OHLCVBar, ...]:
    """Return bars both market-available and ingested by the system by ``cutoff``."""
    normalized_cutoff = ensure_utc(cutoff)
    eligible = (
        bar
        for bar in bars
        if bar.available_at <= normalized_cutoff
        and bar.ingested_at <= normalized_cutoff
        and (include_partial or bar.status is BarStatus.FINAL)
    )
    return tuple(sorted(eligible, key=lambda bar: (bar.open_time, bar.bar_id)))
