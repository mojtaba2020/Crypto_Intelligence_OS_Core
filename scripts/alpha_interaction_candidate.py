"""Deterministic *unfitted* BTC interaction candidate and nested ablation.

Research-only mathematical machinery. Inputs and reviewer assertions in this
module do NOT independently authenticate source vintages, publication times,
training-label maturity, or prospective sample isolation. No network or IO.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import pairwise

from crypto_intelligence_os.hybrid_forecasting import _estimate, _fit


@dataclass(frozen=True)
class HourlyClose:
    """Claimed source metadata for a completed one-hour candle."""

    bar_open_utc: datetime
    close_usd: float
    first_observed_at_utc: datetime


@dataclass(frozen=True)
class FittedComparison:
    """Pure numerical fit, NOT a scientifically approved trained artifact."""

    candidate_fit: tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]
    ablation_fit: tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]
    linearized_placebo_fit: tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]
    training_mean_momentum: float
    training_mean_volatility: float
    additive_projection: tuple[float, float, float]
    independent_interaction: bool
    max_training_interaction_residual: float
    training_rows: int


def interaction_features(
    bars: Sequence[HourlyClose], *, issue_at_utc: datetime
) -> tuple[float, float, float]:
    """Calculate past-only momentum, volatility and interaction from 25 bars.

    The caller supplies timestamps; their independent origin cannot be proven
    by this function. This is intentionally NOT a market data downloader.
    """
    if issue_at_utc.tzinfo is None or issue_at_utc.utcoffset() != timedelta(0):
        raise ValueError("Issue instant must be UTC aware")
    if len(bars) != 25:
        raise ValueError("Exactly 25 consecutive hourly closes required")
    logs: list[float] = []
    prev_open: datetime | None = None
    for bar in bars:
        open_at, observed = bar.bar_open_utc, bar.first_observed_at_utc
        if (
            open_at.tzinfo is None
            or observed.tzinfo is None
            or open_at.utcoffset() != timedelta(0)
            or observed.utcoffset() != timedelta(0)
        ):
            raise ValueError("Bar metadata must be UTC aware")
        if prev_open is not None and open_at - prev_open != timedelta(hours=1):
            raise ValueError("Nonconsecutive hourly candle")
        if observed < open_at + timedelta(hours=1):
            raise ValueError("Purported feature observed before hour completed")
        if observed > issue_at_utc:
            raise ValueError("Feature first observed after issue")
        if (
            not isinstance(bar.close_usd, (int, float))
            or isinstance(bar.close_usd, bool)
            or not math.isfinite(bar.close_usd)
            or bar.close_usd <= 0
        ):
            raise ValueError("Invalid positive close")
        logs.append(math.log(bar.close_usd))
        prev_open = open_at
    if prev_open is None or issue_at_utc < prev_open + timedelta(hours=1):
        raise ValueError("Last feature candle not completed at issue")
    momentum = logs[-1] - logs[0]
    returns = [b - a for a, b in pairwise(logs)]
    volatility = statistics.pstdev(returns)
    interaction = momentum * volatility
    if not all(map(math.isfinite, (momentum, volatility, interaction))):
        raise ValueError("Nonfinite derived feature")
    return momentum, volatility, interaction


def _independent_interaction_projection(
    rows: Sequence[tuple[tuple[float, float, float], float]],
) -> tuple[tuple[float, float, float], bool]:
    """Training-only orthogonal projection onto intercept, momentum, volatility.

    Modified Gram-Schmidt with a second pass accommodates redundant base
    columns. Along with the data-space orthonormal basis, track each basis
    vector's exact representation as a linear combination of base features.
    """
    n = len(rows)
    columns = [
        [1.0] * n,
        [features[0] for features, _ in rows],
        [features[1] for features, _ in rows],
    ]
    basis: list[tuple[list[float], list[float]]] = []
    additive_span_well_conditioned = True
    for index, column in enumerate(columns):
        work = column.copy()
        representation = [float(index == k) for k in range(3)]
        for _ in range(2):
            for unit, linear_coeffs in basis:
                weight = math.fsum(a * b for a, b in zip(work, unit, strict=True))
                work = [a - weight * b for a, b in zip(work, unit, strict=True)]
                representation = [
                    a - weight * b for a, b in zip(representation, linear_coeffs, strict=True)
                ]
        norm = math.sqrt(math.fsum(value * value for value in work))
        source_norm = math.sqrt(math.fsum(value * value for value in column))
        if index == 2:
            # Reject an ill-conditioned additive design: v is nearly a
            # linear function of momentum. Raw projection coefficients
            # become enormous and can amplify small extrapolation errors.
            centered_v = statistics.mean(column)
            variation = math.sqrt(math.fsum((value - centered_v) ** 2 for value in column))
            if variation <= 1e-14 or norm / variation < 0.02:
                additive_span_well_conditioned = False
        if norm <= 1e-10 * max(source_norm, 1e-20):
            continue
        basis.append(
            (
                [value / norm for value in work],
                [value / norm for value in representation],
            )
        )

    interaction = [features[2] for features, _ in rows]
    residual = interaction.copy()
    projection = [0.0, 0.0, 0.0]
    for _ in range(2):
        for unit, linear_coeffs in basis:
            weight = math.fsum(a * b for a, b in zip(residual, unit, strict=True))
            residual = [a - weight * b for a, b in zip(residual, unit, strict=True)]
            projection = [a + weight * b for a, b in zip(projection, linear_coeffs, strict=True)]

    remaining_norm = math.sqrt(math.fsum(value * value for value in residual))
    original_norm = math.sqrt(math.fsum(value * value for value in interaction))
    if not all(math.isfinite(x) for x in projection):
        raise ValueError("Nonfinite additive interaction projection")

    # The model applies raw projection coefficients at inference time.
    # Numerically unstable, nearly collinear data can destroy the
    # orthogonality achieved in data space when reconstructing r.
    reconstructed = [
        z - (projection[0] + projection[1] * m + projection[2] * v) for (m, v, z), _ in rows
    ]
    reconstruction_error = math.sqrt(
        math.fsum((a - b) ** 2 for a, b in zip(reconstructed, residual, strict=True))
    )
    reconstructed_norm = math.sqrt(math.fsum(value * value for value in reconstructed))
    has_incremental_dimension = (
        additive_span_well_conditioned
        and remaining_norm > 1e-6 * max(original_norm, 1e-12)
        and reconstruction_error <= 1e-3 * remaining_norm
        and reconstructed_norm <= 1.001 * remaining_norm
    )
    if has_incremental_dimension:
        # Reject a residual that numerically reintroduces any additive
        # feature direction. Returning False forces exact nested ablation.
        for unit, _coefficients in basis:
            correlation = (
                abs(math.fsum(a * b for a, b in zip(reconstructed, unit, strict=True)))
                / reconstructed_norm
            )
            if correlation > 1e-5:
                has_incremental_dimension = False
                break

    return (projection[0], projection[1], projection[2]), has_incremental_dimension


def fit_candidate_and_controls(
    approved_training_rows: Sequence[tuple[tuple[float, float, float], float]],
    *,
    ridge: float,
) -> FittedComparison:
    """Fit interaction, no-interaction, and shrinkage-matched placebo designs.

    CRITICAL: the caller must independently prove training eligibility and
    target maturity. Passing this numeric function grants NO_RUN only; do not
    infer that these rows are point-in-time valid or free of reserved outcomes.
    """
    if len(approved_training_rows) < 30:
        raise ValueError("At least 30 approved training examples required")
    if not math.isfinite(ridge) or ridge <= 0:
        raise ValueError("Ridge strength must be strictly positive")
    full = []
    nested = []
    for features, label in approved_training_rows:
        if len(features) != 3 or not all(math.isfinite(x) for x in (*features, label)):
            raise ValueError("Nonfinite or wrong-dimensional training row")
        momentum, volatility, interaction = features
        if volatility < 0 or not math.isclose(
            interaction, momentum * volatility, rel_tol=1e-9, abs_tol=1e-12
        ):
            raise ValueError("Malformed interaction feature")
        full.append((features, label))
        nested.append(((momentum, volatility), label))
    mean_m = statistics.mean(features[0] for features, _ in full)
    mean_v = statistics.mean(features[1] for features, _ in full)
    # This Taylor-linearized feature is a predeclared negative control for
    # ridge penalty relief caused by adding a redundant correlated column.
    # When either m or v is constant, it equals m*v on every row.
    placebo = [
        ((m, v, m * mean_v + mean_m * v - mean_m * mean_v), y) for (m, v, _interaction), y in full
    ]
    projection, enabled = _independent_interaction_projection(full)
    candidate_rows = [
        (
            (
                m,
                v,
                z - (projection[0] + projection[1] * m + projection[2] * v) if enabled else 0.0,
            ),
            y,
        )
        for (m, v, z), y in full
    ]
    return FittedComparison(
        candidate_fit=_fit(candidate_rows, ridge=ridge),
        ablation_fit=_fit(nested, ridge=ridge),
        linearized_placebo_fit=_fit(placebo, ridge=ridge),
        training_mean_momentum=mean_m,
        training_mean_volatility=mean_v,
        additive_projection=projection,
        independent_interaction=enabled,
        max_training_interaction_residual=max(abs(features[2]) for features, _ in candidate_rows),
        training_rows=len(full),
    )


def predict_log_returns(
    model_pair: FittedComparison, features: tuple[float, float, float]
) -> tuple[float, float, float, float]:
    """Return candidate, ablation, linearized placebo and persistence returns."""
    if len(features) != 3 or not all(math.isfinite(v) for v in features):
        raise ValueError("Invalid feature vector")
    momentum, volatility, interaction = features
    if volatility < 0 or not math.isclose(
        interaction, momentum * volatility, rel_tol=1e-9, abs_tol=1e-12
    ):
        raise ValueError("Invalid interaction feature")
    offset, slope_m, slope_v = model_pair.additive_projection
    residual = (
        interaction - (offset + slope_m * momentum + slope_v * volatility)
        if model_pair.independent_interaction
        else 0.0
    )
    ablation = _estimate(*model_pair.ablation_fit, (momentum, volatility))
    # Never evaluate a learned interaction far outside the residual range
    # seen at training time. A no-signal fallback must be disclosed in an
    # eventual scheduled-origin record; it cannot count as a model victory.
    extrapolated = (
        model_pair.independent_interaction
        and abs(residual) > 4.0 * model_pair.max_training_interaction_residual
    )
    candidate = (
        ablation
        if extrapolated
        else _estimate(*model_pair.candidate_fit, (momentum, volatility, residual))
    )
    placebo_feature = (
        momentum * model_pair.training_mean_volatility
        + volatility * model_pair.training_mean_momentum
        - model_pair.training_mean_momentum * model_pair.training_mean_volatility
    )
    placebo = _estimate(*model_pair.linearized_placebo_fit, (momentum, volatility, placebo_feature))
    if not all(math.isfinite(v) for v in (candidate, ablation, placebo)):
        raise ValueError("Nonfinite model output")
    return candidate, ablation, placebo, 0.0


if __name__ == "__main__":
    raise SystemExit("Research library only: no CLI, data access or forecast dispatch")
