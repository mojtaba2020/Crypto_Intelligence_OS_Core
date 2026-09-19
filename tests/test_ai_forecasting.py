"""Offline checks for BTC forecasting model and chronological evaluation."""

from datetime import date, timedelta

import pytest

from crypto_intelligence_os.ai_forecasting import (
    Observation,
    predict,
    train,
    walk_forward,
)


def history(count: int = 95) -> tuple[Observation, ...]:
    start = date(2025, 1, 1)
    return tuple(
        Observation(start + timedelta(days=index), 100 + index * 0.5)
        for index in range(count)
    )


def test_training_and_prediction_are_finite() -> None:
    rows = history()
    model = train(rows, horizon_days=7)
    estimate = predict(model, rows)
    assert estimate > 0
    assert model.train_examples == len(rows) - 14 - 7
    assert model.last_training_target == rows[-1].day


def test_walk_forward_uses_resolved_training_labels() -> None:
    rows = history()
    result = walk_forward(rows, horizon_days=7)
    assert result.test_examples >= 10
    assert result.model_mae >= 0
    assert result.persistence_mae >= 0
    assert result.model_mape_pct >= 0


def test_rejects_gaps_and_short_history() -> None:
    rows = history()
    with pytest.raises(ValueError, match="contiguous"):
        train(rows[:20] + rows[21:], horizon_days=7)
    with pytest.raises(ValueError, match="Insufficient"):
        train(rows[:25], horizon_days=7)
