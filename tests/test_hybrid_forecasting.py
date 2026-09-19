"""Leakage-safe tests for independently recorded forecasts and their ensemble."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from crypto_intelligence_os.hybrid_forecasting import (
    Forecast,
    Realization,
    evaluate_hybrid,
)


BASE = datetime(2025, 1, 1, tzinfo=UTC)


def test_no_future_target_is_used_to_fit_weight() -> None:
    forecasts = (
        Forecast("mojtaba", BASE, BASE + timedelta(days=1), Decimal("100")),
        Forecast("ai", BASE, BASE + timedelta(days=1), Decimal("200")),
        Forecast(
            "mojtaba",
            BASE + timedelta(days=1),
            BASE + timedelta(days=2),
            Decimal("100"),
        ),
        Forecast(
            "ai",
            BASE + timedelta(days=1),
            BASE + timedelta(days=2),
            Decimal("200"),
        ),
    )
    actuals = (
        Realization(BASE + timedelta(days=1), Decimal("200")),
        Realization(BASE + timedelta(days=2), Decimal("200")),
    )
    result = evaluate_hybrid(forecasts, actuals, minimum_training_pairs=1)
    assert result[0].ai_weight == Decimal("0.5")
    assert result[1].ai_weight == Decimal("0.5")
    assert result[1].training_pairs == 0


def test_past_resolved_target_can_train_next_forecast() -> None:
    forecasts = (
        Forecast("mojtaba", BASE, BASE + timedelta(days=1), Decimal("100")),
        Forecast("ai", BASE, BASE + timedelta(days=1), Decimal("200")),
        Forecast(
            "mojtaba",
            BASE + timedelta(days=2),
            BASE + timedelta(days=3),
            Decimal("100"),
        ),
        Forecast(
            "ai",
            BASE + timedelta(days=2),
            BASE + timedelta(days=3),
            Decimal("200"),
        ),
    )
    actuals = (Realization(BASE + timedelta(days=1), Decimal("200")),)
    result = evaluate_hybrid(forecasts, actuals, minimum_training_pairs=1)
    assert result[1].training_pairs == 1
    assert result[1].ai_weight == Decimal(1)
    assert result[1].hybrid_price == Decimal(200)
    assert result[1].actual_price is None
    assert result[1].hybrid_absolute_error is None


def test_invalid_future_issued_forecast_is_rejected() -> None:
    with pytest.raises(ValueError, match="precede"):
        evaluate_hybrid(
            (Forecast("ai", BASE, BASE, Decimal(100)),),
            (),
        )
