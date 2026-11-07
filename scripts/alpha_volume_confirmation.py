"""One additional falsifiable BTC hypothesis: volume-confirmed 4h momentum.

This is an UNVALIDATED research candidate and does not claim predictive edge.
Volume in Coinbase Exchange 1h OHLCV is BTC base-asset volume, not order flow.
No live API, no CI deployments, no trading and no source-vintage authentication.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from crypto_intelligence_os.hybrid_forecasting import _estimate, _fit
from scripts.alpha_4h_training_bridge import (
    FiveMinuteTarget,
    make_matured_example,
)
from scripts.alpha_interaction_candidate import (
    HourlyClose,
    _independent_interaction_projection,
)


@dataclass(frozen=True)
class HourlyVolumeBar:
    bar_open_utc: datetime
    close_usd: float
    base_volume_btc: float
    first_observed_at_utc: datetime


@dataclass(frozen=True)
class VolumeTrainingRow:
    origin_utc: datetime
    issued_at_utc: datetime
    target_first_observed_at_utc: datetime
    reference_close_usd: float
    features: tuple[float, float, float]
    realized_log_return: float


@dataclass(frozen=True)
class VolumeScore:
    origin_utc: datetime
    eligible_training_rows: int
    candidate_log_return: float
    additive_log_return: float
    momentum_log_return: float
    realized_log_return: float
    candidate_abs_log_error: float
    additive_abs_log_error: float
    momentum_abs_log_error: float
    persistence_abs_log_error: float
    interaction_active: bool


@dataclass(frozen=True)
class VolumeReplay:
    supplied_origins: int
    expected_origins_between_bounds: int
    missing_origin_slots: int
    cold_start_origins: int
    scored: tuple[VolumeScore, ...]


def _utc(dt: datetime) -> None:
    if not isinstance(dt, datetime) or dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError("all source timestamps must be timezone-aware UTC")


def volume_confirmation_features(
    bars: Sequence[HourlyVolumeBar], *, issued_at_utc: datetime
) -> tuple[float, float, float]:
    """Use only 25 completed hourly BTC closes and volumes at the issue time.

    x0 = 4h close-to-close log momentum.
    x1 = log(recent 4h volume / (previous 20h volume / 5)).
    x2 = momentum * relative-volume log shock (orthogonalized when fitted).
    Reject zero-volume bars instead of inventing a continuation price.
    """
    _utc(issued_at_utc)
    if len(bars) != 25:
        raise ValueError("exactly 25 completed hourly OHLCV candles required")
    last: datetime | None = None
    for bar in bars:
        _utc(bar.bar_open_utc)
        _utc(bar.first_observed_at_utc)
        if last is not None and bar.bar_open_utc - last != timedelta(hours=1):
            raise ValueError("nonconsecutive hourly OHLCV candles")
        if not bar.bar_open_utc + timedelta(hours=1) <= bar.first_observed_at_utc <= issued_at_utc:
            raise ValueError("OHLCV candle not completed/available by forecast issue")
        if (
            isinstance(bar.close_usd, bool)
            or isinstance(bar.base_volume_btc, bool)
            or not isinstance(bar.close_usd, (int, float))
            or not isinstance(bar.base_volume_btc, (int, float))
            or not math.isfinite(bar.close_usd)
            or not math.isfinite(bar.base_volume_btc)
            or bar.close_usd <= 0
            or bar.base_volume_btc <= 0
        ):
            raise ValueError("OHLCV needs finite positive close and BTC volume")
        last = bar.bar_open_utc
    m = math.log(bars[-1].close_usd / bars[-5].close_usd)
    recent_4h = math.fsum(bar.base_volume_btc for bar in bars[-4:])
    preceding_20h = math.fsum(bar.base_volume_btc for bar in bars[1:21])
    v = math.log(recent_4h / (preceding_20h / 5.0))
    z = m * v
    if not all(map(math.isfinite, (m, v, z))):
        raise ValueError("nonfinite volume feature")
    return m, v, z


def make_volume_training_row(
    bars: Sequence[HourlyVolumeBar],
    *,
    origin_utc: datetime,
    issued_at_utc: datetime,
    target: FiveMinuteTarget,
    fit_at_utc: datetime,
) -> VolumeTrainingRow:
    """Reuse the exact S+4h15m target/receipt guard from the 4h bridge."""
    proxy = [
        HourlyClose(bar.bar_open_utc, bar.close_usd, bar.first_observed_at_utc)
        for bar in bars
    ]
    mature = make_matured_example(
        proxy,
        origin_utc=origin_utc,
        issued_at_utc=issued_at_utc,
        target=target,
        fit_at_utc=fit_at_utc,
    )
    volume_features = volume_confirmation_features(bars, issued_at_utc=issued_at_utc)
    return VolumeTrainingRow(
        origin_utc=origin_utc,
        issued_at_utc=issued_at_utc,
        target_first_observed_at_utc=mature.target_first_observed_at_utc,
        reference_close_usd=mature.reference_close_usd,
        features=volume_features,
        realized_log_return=mature.realized_log_return,
    )


def walk_forward_volume_candidate(
    examples: Sequence[VolumeTrainingRow], *, ridge: float = 100.0
) -> VolumeReplay:
    """Compare fixed, expanding-window models without seeing future labels.

    Candidate: x=(m, v, r), with r the training-only orthogonal residual
    of m*v beyond the additive span (1,m,v); if redundant, r is fixed to 0.
    Controls: additive (m,v), momentum-only (m), Persistence (zero return).
    All use exactly the same fully-mature training set and fixed ridge.
    """
    if not 2 <= len(examples) <= 512:
        raise ValueError("requires 2..512 distinct development origins")
    if not math.isfinite(ridge) or ridge <= 0:
        raise ValueError("positive finite ridge required")
    rows = sorted(examples, key=lambda row: row.origin_utc)
    origins: set[datetime] = set()
    for row in rows:
        if not isinstance(row, VolumeTrainingRow):
            raise ValueError("unrecognized volume training row")
        _utc(row.origin_utc)
        _utc(row.issued_at_utc)
        _utc(row.target_first_observed_at_utc)
        if (
            row.origin_utc.hour % 4 != 0
            or row.origin_utc.minute != 0
            or row.origin_utc.second != 0
            or row.origin_utc.microsecond != 0
            or not row.origin_utc <= row.issued_at_utc <= row.origin_utc + timedelta(minutes=15)
            or row.target_first_observed_at_utc < row.origin_utc + timedelta(hours=4, minutes=15)
        ):
            raise ValueError("invalid origin or target maturity")
        if row.origin_utc in origins:
            raise ValueError("duplicate four-hour origin")
        origins.add(row.origin_utc)
        m, v, z = row.features
        if (
            not all(map(math.isfinite, (m, v, z, row.realized_log_return)))
            or not math.isclose(z, m * v, rel_tol=1e-9, abs_tol=1e-12)
        ):
            raise ValueError("invalid volume research features or label")

    scored: list[VolumeScore] = []
    skipped = 0
    for index, current in enumerate(rows):
        past = [
            row for row in rows[:index]
            if row.target_first_observed_at_utc <= current.issued_at_utc
        ]
        if len(past) < 30:
            skipped += 1
            continue
        triples = [(row.features, row.realized_log_return) for row in past]
        projection, enabled = _independent_interaction_projection(triples)
        shift, slope_m, slope_v = projection

        def residual(m: float, v: float, z: float) -> float:
            return z - (shift + slope_m * m + slope_v * v) if enabled else 0.0

        full = [
            ((m, v, residual(m, v, z)), y)
            for (m, v, z), y in triples
        ]
        additive = [((m, v), y) for (m, v, _), y in triples]
        momentum = [((m,), y) for (m, _, _), y in triples]
        candidate_fit = _fit(full, ridge=ridge)
        additive_fit = _fit(additive, ridge=ridge)
        momentum_fit = _fit(momentum, ridge=ridge)
        m, v, z = current.features
        forecasts = (
            _estimate(*candidate_fit, (m, v, residual(m, v, z))),
            _estimate(*additive_fit, (m, v)),
            _estimate(*momentum_fit, (m,)),
            0.0,
        )
        if not all(map(math.isfinite, forecasts)):
            raise ValueError("nonfinite walk-forward forecasts")
        errors = tuple(abs(pred - current.realized_log_return) for pred in forecasts)
        scored.append(
            VolumeScore(
                origin_utc=current.origin_utc,
                eligible_training_rows=len(past),
                candidate_log_return=forecasts[0],
                additive_log_return=forecasts[1],
                momentum_log_return=forecasts[2],
                realized_log_return=current.realized_log_return,
                candidate_abs_log_error=errors[0],
                additive_abs_log_error=errors[1],
                momentum_abs_log_error=errors[2],
                persistence_abs_log_error=errors[3],
                interaction_active=enabled,
            )
        )
    expected = int((rows[-1].origin_utc - rows[0].origin_utc) / timedelta(hours=4)) + 1
    return VolumeReplay(
        supplied_origins=len(rows),
        expected_origins_between_bounds=expected,
        missing_origin_slots=expected - len(rows),
        cold_start_origins=skipped,
        scored=tuple(scored),
    )
