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
        Observation(start + timedelta(days=index), 100 + index * 0.5) for index in range(count)
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


def test_training_cannot_see_unresolved_future_targets() -> None:
    rows = history(105)
    origin = 70
    first = train(rows[: origin + 1], horizon_days=7)
    assert first.last_training_target == rows[origin].day
    assert first.train_examples == origin - 14 - 7 + 1
    # A changed future price must not change any forecast made at this origin.
    revised = rows[: origin + 1] + tuple(
        Observation(point.day, point.close * 10) for point in rows[origin + 1 :]
    )
    second = train(revised[: origin + 1], horizon_days=7)
    assert second == first
    assert predict(first, revised[: origin + 1]) == predict(first, rows[: origin + 1])


def test_walk_forward_is_invariant_to_unseen_future() -> None:
    rows = history(105)
    # Change only the last completed close. Earlier forecasts and targets
    # must be identical; only the final origin/target pair may change.
    amended = rows[:-1] + (Observation(rows[-1].day, rows[-1].close * 10),)
    horizon = 7
    earlier = walk_forward(rows[:-horizon], horizon_days=horizon)
    amended_earlier = walk_forward(amended[:-horizon], horizon_days=horizon)
    assert earlier.model_mae == amended_earlier.model_mae
    assert earlier.persistence_mae == amended_earlier.persistence_mae
    assert earlier.test_examples == amended_earlier.test_examples


def test_walk_forward_reports_overlapping_test_origins() -> None:
    rows = history(105)
    horizon = 7
    result = walk_forward(rows, horizon_days=horizon)
    first_origin = 14 + horizon + 30 - 1
    last_origin = len(rows) - horizon - 1
    assert result.test_examples == last_origin - first_origin + 1
    assert rows[first_origin + horizon].day > rows[first_origin + 1].day
    # Adjacent test windows share observations: raw test count is not an
    # independent-sample count for uncertainty intervals or significance.
