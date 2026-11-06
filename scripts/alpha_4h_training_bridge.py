"""Research-only temporal bridge for the 4-hour Alpha candidate.

Caller-provided timestamps are UNAUTHENTICATED assertions. This provides no
independent custody, certified first publication, or Stage-6 GO. No market IO.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from scripts.alpha_interaction_candidate import (
    FittedComparison,
    HourlyClose,
    fit_candidate_and_controls,
    interaction_features,
    predict_with_diagnostics,
)


@dataclass(frozen=True)
class FiveMinuteTarget:
    """Claimed complete five-minute BTC target and receipt time."""

    bar_open_utc: datetime
    close_usd: float
    first_observed_at_utc: datetime


@dataclass(frozen=True)
class MaturedExample:
    """Numerically eligible training row; source authenticity is NOT proven."""

    origin_utc: datetime
    issued_at_utc: datetime
    target_first_observed_at_utc: datetime
    reference_close_usd: float
    features: tuple[float, float, float]
    realized_log_return: float


@dataclass(frozen=True)
class TrainedComparison:
    """An internal fitted model with the claimed fit instant retained."""

    fitted_at_utc: datetime
    numerical_fit: FittedComparison
    training_rows: int


@dataclass(frozen=True)
class UnscoredForecast:
    """Local model predictions, NOT prospective publicly issued forecasts."""

    origin_utc: datetime
    issued_at_utc: datetime
    candidate_usd: float
    ablation_usd: float
    placebo_usd: float
    persistence_usd: float
    interaction_applied: bool
    fallback_reason: str | None


def _utc(value: datetime, name: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{name} must be an aware UTC datetime")


def _origin(origin: datetime, issued_at: datetime) -> None:
    _utc(origin, "origin")
    _utc(issued_at, "issued_at")
    if any((origin.minute, origin.second, origin.microsecond)) or origin.hour % 4 != 0:
        raise ValueError("origin must be on fixed 00/04/08/12/16/20 UTC clock")
    if not origin <= issued_at <= origin + timedelta(minutes=15):
        raise ValueError("issue must be within S..S+15m, never backdated")


def _features(
    bars: Sequence[HourlyClose], origin: datetime, issued_at: datetime
) -> tuple[float, float, float]:
    if len(bars) != 25 or bars[-1].bar_open_utc != origin - timedelta(hours=1):
        raise ValueError("25 bars must end at the fixed S origin")
    return interaction_features(bars, issue_at_utc=issued_at)


def make_matured_example(
    bars: Sequence[HourlyClose],
    *,
    origin_utc: datetime,
    issued_at_utc: datetime,
    target: FiveMinuteTarget,
    fit_at_utc: datetime,
) -> MaturedExample:
    """Create one training label only after the fixed S+4h15m target matures."""
    _origin(origin_utc, issued_at_utc)
    _utc(fit_at_utc, "fit_at")
    _utc(target.bar_open_utc, "target bar open")
    _utc(target.first_observed_at_utc, "target first observed")
    if fit_at_utc < issued_at_utc:
        raise ValueError("fit cannot precede the claimed forecast issue")
    features = _features(bars, origin_utc, issued_at_utc)
    target_end = origin_utc + timedelta(hours=4, minutes=15)
    if target.bar_open_utc != target_end - timedelta(minutes=5):
        raise ValueError("wrong fixed 4h15m five-minute target interval")
    if target.first_observed_at_utc < target_end:
        raise ValueError("target allegedly observed before close")
    if target.first_observed_at_utc > fit_at_utc:
        raise ValueError("unmatured future target cannot be used for fitting")
    if (
        isinstance(target.close_usd, bool)
        or not isinstance(target.close_usd, (float, int))
        or not math.isfinite(target.close_usd)
        or target.close_usd <= 0
    ):
        raise ValueError("target close must be a positive finite USD price")
    label = math.log(target.close_usd / bars[-1].close_usd)
    if not math.isfinite(label):
        raise ValueError("nonfinite log-return target")
    return MaturedExample(
        origin_utc=origin_utc,
        issued_at_utc=issued_at_utc,
        target_first_observed_at_utc=target.first_observed_at_utc,
        reference_close_usd=float(bars[-1].close_usd),
        features=features,
        realized_log_return=label,
    )


def fit_matured_comparisons(
    examples: Sequence[MaturedExample], *, fit_at_utc: datetime, ridge: float
) -> TrainedComparison:
    """Fit existing candidate + ablation + placebo on matured development rows.

    Source provenance and protected-OOS isolation must be established separately.
    This does not authorize a Stage-6 empirical experiment.
    """
    _utc(fit_at_utc, "fit_at")
    if len(examples) < 30:
        raise ValueError("at least 30 matured examples required")
    origins: set[datetime] = set()
    checked_rows: list[MaturedExample] = []
    for row in examples:
        if not isinstance(row, MaturedExample):
            raise ValueError("invalid example record")
        _origin(row.origin_utc, row.issued_at_utc)
        _utc(row.target_first_observed_at_utc, "label observed")
        if row.origin_utc in origins:
            raise ValueError("duplicate training origin")
        if row.target_first_observed_at_utc < row.origin_utc + timedelta(hours=4, minutes=15):
            raise ValueError("target observed before scheduled target close")
        if row.target_first_observed_at_utc > fit_at_utc:
            raise ValueError("training uses an unmatured future label")
        if not math.isfinite(row.realized_log_return):
            raise ValueError("nonfinite training target")
        origins.add(row.origin_utc)
        checked_rows.append(row)
    checked_rows.sort(key=lambda row: row.origin_utc)
    numeric_rows = [(row.features, row.realized_log_return) for row in checked_rows]
    numerical = fit_candidate_and_controls(numeric_rows, ridge=ridge)
    return TrainedComparison(
        fitted_at_utc=fit_at_utc,
        numerical_fit=numerical,
        training_rows=numerical.training_rows,
    )


def predict_unscored_four_hour(
    model: TrainedComparison,
    bars: Sequence[HourlyClose],
    *,
    origin_utc: datetime,
    issued_at_utc: datetime,
) -> UnscoredForecast:
    """Return four positive USD prices without issuing or publishing forecasts."""
    _origin(origin_utc, issued_at_utc)
    if not isinstance(model, TrainedComparison):
        raise ValueError("model must carry the original fit timestamp")
    _utc(model.fitted_at_utc, "model fit time")
    if model.fitted_at_utc > issued_at_utc:
        raise ValueError("model was fitted after prediction issue (lookahead)")
    features = _features(bars, origin_utc, issued_at_utc)
    details = predict_with_diagnostics(model.numerical_fit, features)
    current = float(bars[-1].close_usd)
    try:
        prices = tuple(current * math.exp(value) for value in details.returns())
    except OverflowError as exc:
        raise ValueError("model produced price overflow") from exc
    if not all(math.isfinite(value) and value > 0 for value in prices):
        raise ValueError("model produced invalid positive USD price")
    return UnscoredForecast(
        origin_utc=origin_utc,
        issued_at_utc=issued_at_utc,
        candidate_usd=prices[0],
        ablation_usd=prices[1],
        placebo_usd=prices[2],
        persistence_usd=prices[3],
        interaction_applied=details.interaction_applied,
        fallback_reason=details.fallback_reason,
    )
