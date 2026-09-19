"""Leakage-aware hybrid forecast evaluation; separate user and AI forecasts.

Only predictions issued before their target and with realized target prices
can be evaluated. Weights are fitted on strictly earlier resolved targets.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal


ModelName = Literal["mojtaba", "ai"]


@dataclass(frozen=True)
class Forecast:
    model: ModelName
    issued_at: datetime
    target_at: datetime
    predicted_price: Decimal


@dataclass(frozen=True)
class Realization:
    target_at: datetime
    actual_price: Decimal


@dataclass(frozen=True)
class HybridResult:
    issued_at: datetime
    target_at: datetime
    mojtaba_price: Decimal
    ai_price: Decimal
    hybrid_price: Decimal
    ai_weight: Decimal
    actual_price: Decimal | None
    mojtaba_absolute_error: Decimal | None
    ai_absolute_error: Decimal | None
    hybrid_absolute_error: Decimal | None
    training_pairs: int


def _valid_price(price: Decimal) -> bool:
    return price.is_finite() and price > 0


def evaluate_hybrid(
    forecasts: tuple[Forecast, ...],
    realizations: tuple[Realization, ...],
    *,
    minimum_training_pairs: int = 10,
) -> tuple[HybridResult, ...]:
    """Fit nonnegative convex ensemble weight using prior resolved paired errors.

    Each target is evaluated independently. Training pairs must have target_at
    strictly before the new forecast's issued_at, preventing future leakage.
    Unresolved forecasts have no actual or error. A 50/50 blend is used until
    enough prior pairs exist. The resulting weight minimizes historical squared
    price error, with a simple grid of 101 candidate weights.
    """
    if minimum_training_pairs < 1:
        raise ValueError("minimum_training_pairs must be positive")
    actuals: dict[datetime, Decimal] = {}
    for row in realizations:
        if row.target_at.tzinfo is None or not _valid_price(row.actual_price):
            raise ValueError("Invalid realization")
        if row.target_at in actuals and actuals[row.target_at] != row.actual_price:
            raise ValueError("Conflicting actual price")
        actuals[row.target_at] = row.actual_price

    pairs: dict[tuple[datetime, datetime], dict[str, Decimal]] = {}
    for forecast in forecasts:
        if forecast.issued_at.tzinfo is None or forecast.target_at.tzinfo is None:
            raise ValueError("Forecast timestamps must be timezone-aware")
        if forecast.issued_at >= forecast.target_at or not _valid_price(
            forecast.predicted_price
        ):
            raise ValueError("Forecast must precede its target and have a valid price")
        if forecast.model not in ("mojtaba", "ai"):
            raise ValueError("Unknown model")
        pair = pairs.setdefault((forecast.issued_at, forecast.target_at), {})
        if forecast.model in pair and pair[forecast.model] != forecast.predicted_price:
            raise ValueError("Conflicting forecast for model and timestamps")
        pair[forecast.model] = forecast.predicted_price

    complete = [
        (issued, target, models["mojtaba"], models["ai"])
        for (issued, target), models in pairs.items()
        if "mojtaba" in models and "ai" in models
    ]
    output: list[HybridResult] = []
    for issued, target, moj, ai in sorted(complete):
        history = [
            (past_moj, past_ai, actuals[past_target])
            for past_issued, past_target, past_moj, past_ai in complete
            if past_target < issued
            and past_target in actuals
            and past_issued < past_target
        ]
        weight = Decimal("0.5")
        if len(history) >= minimum_training_pairs:
            candidates = (Decimal(i) / 100 for i in range(101))
            weight = min(
                candidates,
                key=lambda w: sum(
                    ((Decimal(1) - w) * m + w * a - actual) ** 2
                    for m, a, actual in history
                ),
            )
        hybrid = (Decimal(1) - weight) * moj + weight * ai
        actual = actuals.get(target)
        output.append(
            HybridResult(
                issued_at=issued,
                target_at=target,
                mojtaba_price=moj,
                ai_price=ai,
                hybrid_price=hybrid,
                ai_weight=weight,
                actual_price=actual,
                mojtaba_absolute_error=abs(moj - actual) if actual is not None else None,
                ai_absolute_error=abs(ai - actual) if actual is not None else None,
                hybrid_absolute_error=(
                    abs(hybrid - actual) if actual is not None else None
                ),
                training_pairs=len(history),
            )
        )
    return tuple(output)
