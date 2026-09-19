"""Mojtaba's cycle-research calculations, intentionally separate from AI models.

The caller supplies validated historical peaks/troughs and halving timestamps.
This module measures ratios, calendar-day gaps, halving distances, and price-band
occupancy. It does not infer extrema and does not claim predictive probability.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from itertools import pairwise
from typing import Literal


ExtremumKind = Literal["peak", "trough"]


@dataclass(frozen=True)
class Extremum:
    kind: ExtremumKind
    time: datetime
    price: Decimal
    label: str = ""


@dataclass(frozen=True)
class HalvingEvent:
    time: datetime
    label: str


@dataclass(frozen=True)
class DailyClose:
    day: date
    close: Decimal
    source: str


@dataclass(frozen=True)
class ExtremumRatio:
    relation: str
    first_label: str
    second_label: str
    first_time: datetime
    second_time: datetime
    first_price: Decimal
    second_price: Decimal
    price_ratio: Decimal
    percent_change: Decimal
    days_apart: int


@dataclass(frozen=True)
class HalvingDistance:
    halving_label: str
    extremum_label: str
    extremum_kind: ExtremumKind
    signed_days_from_halving: int
    absolute_days_from_halving: int
    extremum_price: Decimal


@dataclass(frozen=True)
class PriceBand:
    label: str
    lower: Decimal
    upper: Decimal


@dataclass(frozen=True)
class StabilizationEpisode:
    band_label: str
    start_day: date
    end_day: date
    days: int


@dataclass(frozen=True)
class PriceBandStats:
    source: str
    band_label: str
    lower: Decimal
    upper: Decimal
    total_days_present: int
    episode_count: int
    longest_episode_days: int
    stable_episode_count: int
    stable_days: int
    entries: int
    exits: int
    episodes: tuple[StabilizationEpisode, ...]


PRICE_BANDS: tuple[PriceBand, ...] = (
    PriceBand("0-10", Decimal("0"), Decimal("10")),
    PriceBand("10-100", Decimal("10"), Decimal("100")),
    PriceBand("100-1000", Decimal("100"), Decimal("1000")),
    PriceBand("1000-10000", Decimal("1000"), Decimal("10000")),
    PriceBand("10000-100000", Decimal("10000"), Decimal("100000")),
    PriceBand("100000-1000000", Decimal("100000"), Decimal("1000000")),
)


def _validate_extrema(extrema: tuple[Extremum, ...]) -> None:
    for point in extrema:
        if point.kind not in ("peak", "trough"):
            raise ValueError("Extremum kind must be peak or trough")
        if point.time.tzinfo is None:
            raise ValueError("Extremum timestamps must be timezone-aware")
        if not point.price.is_finite() or point.price <= 0:
            raise ValueError("Extremum prices must be finite and positive")


def _ratio(first: Extremum, second: Extremum, relation: str) -> ExtremumRatio:
    ratio = second.price / first.price
    return ExtremumRatio(
        relation=relation,
        first_label=first.label,
        second_label=second.label,
        first_time=first.time,
        second_time=second.time,
        first_price=first.price,
        second_price=second.price,
        price_ratio=ratio,
        percent_change=(ratio - 1) * 100,
        days_apart=(second.time.date() - first.time.date()).days,
    )


def extremum_relationships(
    extrema: tuple[Extremum, ...],
) -> tuple[ExtremumRatio, ...]:
    """Measure consecutive peak/peak, trough/trough, and alternating relationships."""
    _validate_extrema(extrema)
    ordered = tuple(sorted(extrema, key=lambda point: point.time))
    if len({(point.kind, point.time) for point in ordered}) != len(ordered):
        raise ValueError("Duplicate extremum kind/timestamp")

    output: list[ExtremumRatio] = []
    for kind in ("peak", "trough"):
        same_kind = [point for point in ordered if point.kind == kind]
        for first, second in pairwise(same_kind):
            output.append(_ratio(first, second, f"{kind}_to_{kind}"))

    for first, second in pairwise(ordered):
        if first.kind == second.kind:
            continue
        output.append(_ratio(first, second, f"{first.kind}_to_{second.kind}"))
    return tuple(sorted(output, key=lambda row: (row.second_time, row.relation)))


def halving_distances(
    halvings: tuple[HalvingEvent, ...],
    extrema: tuple[Extremum, ...],
) -> tuple[HalvingDistance, ...]:
    """Return signed day distance from every halving to every supplied extremum."""
    _validate_extrema(extrema)
    output: list[HalvingDistance] = []
    for halving in halvings:
        if halving.time.tzinfo is None:
            raise ValueError("Halving timestamps must be timezone-aware")
        for point in extrema:
            signed = (point.time.date() - halving.time.date()).days
            output.append(
                HalvingDistance(
                    halving_label=halving.label,
                    extremum_label=point.label,
                    extremum_kind=point.kind,
                    signed_days_from_halving=signed,
                    absolute_days_from_halving=abs(signed),
                    extremum_price=point.price,
                )
            )
    return tuple(output)


def _band_for_price(
    close: Decimal,
    bands: tuple[PriceBand, ...],
) -> PriceBand | None:
    for band in bands:
        if band.lower <= close < band.upper:
            return band
    return None


def price_band_stabilization(
    closes: tuple[DailyClose, ...],
    *,
    minimum_stable_days: int = 1,
    bands: tuple[PriceBand, ...] = PRICE_BANDS,
) -> tuple[PriceBandStats, ...]:
    """Measure daily presence and consecutive stabilization episodes per price band.

    A day belongs to [lower, upper), so an exact boundary is counted only once.
    Gaps in the daily series break an episode. Sources are never mixed.
    """
    if minimum_stable_days <= 0:
        raise ValueError("minimum_stable_days must be positive")

    history: dict[str, dict[date, Decimal]] = {}
    for candle in closes:
        if not candle.source:
            raise ValueError("Source must be non-empty")
        if not candle.close.is_finite() or candle.close <= 0:
            raise ValueError("Daily close must be finite and positive")
        source_days = history.setdefault(candle.source, {})
        if candle.day in source_days and source_days[candle.day] != candle.close:
            raise ValueError("Conflicting close for source/day")
        source_days[candle.day] = candle.close

    output: list[PriceBandStats] = []
    for source, source_days in sorted(history.items()):
        ordered_days = sorted(source_days)
        episodes_by_band: dict[str, list[StabilizationEpisode]] = {
            band.label: [] for band in bands
        }
        entries_by_band = {band.label: 0 for band in bands}
        exits_by_band = {band.label: 0 for band in bands}
        current_band: PriceBand | None = None
        episode_start: date | None = None
        previous_day: date | None = None

        def close_episode(
            end_day: date | None,
            *,
            observed_exit: bool = False,
        ) -> None:
            nonlocal current_band, episode_start
            if current_band is None or episode_start is None or end_day is None:
                return
            days = (end_day - episode_start).days + 1
            episodes_by_band[current_band.label].append(
                StabilizationEpisode(
                    band_label=current_band.label,
                    start_day=episode_start,
                    end_day=end_day,
                    days=days,
                )
            )
            if observed_exit:
                exits_by_band[current_band.label] += 1
            current_band = None
            episode_start = None

        for day in ordered_days:
            band = _band_for_price(source_days[day], bands)
            is_gap = previous_day is not None and day != previous_day + timedelta(days=1)
            previous_band = current_band
            if is_gap:
                close_episode(previous_day)
                previous_band = None
            if band != current_band:
                if current_band is not None:
                    close_episode(previous_day, observed_exit=True)
                if band is not None:
                    current_band = band
                    episode_start = day
                    if previous_day is not None and not is_gap and previous_band != band:
                        entries_by_band[band.label] += 1
            previous_day = day
        close_episode(previous_day)

        for band in bands:
            episodes = tuple(episodes_by_band[band.label])
            stable = tuple(
                episode for episode in episodes if episode.days >= minimum_stable_days
            )
            total_days = sum(episode.days for episode in episodes)
            output.append(
                PriceBandStats(
                    source=source,
                    band_label=band.label,
                    lower=band.lower,
                    upper=band.upper,
                    total_days_present=total_days,
                    episode_count=len(episodes),
                    longest_episode_days=max((episode.days for episode in episodes), default=0),
                    stable_episode_count=len(stable),
                    stable_days=sum(episode.days for episode in stable),
                    entries=entries_by_band[band.label],
                    exits=exits_by_band[band.label],
                    episodes=episodes,
                )
            )
    return tuple(output)
