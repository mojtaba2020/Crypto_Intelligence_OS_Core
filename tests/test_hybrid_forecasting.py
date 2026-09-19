"""Contract tests for hybrid BTC research forecasts."""

from datetime import date, timedelta

import pytest

from crypto_intelligence_os.ai_forecasting import Observation
from crypto_intelligence_os.hybrid_forecasting import features, predict_hybrid, train_hybrid


def _history(days: int = 1000) -> tuple[Observation, ...]:
    start = date(2020, 1, 1)
    return tuple(
        Observation(start + timedelta(days=index), 10000.0 + index * 10.0) for index in range(days)
    )


def test_hybrid_training_and_prediction() -> None:
    history = _history()
    model = train_hybrid(history)
    assert model.train_examples == len(history) - 365 - model.horizon_days
    assert model.blend in (0.0, 0.25, 0.5, 0.75, 1.0)
    assert predict_hybrid(model, history) > 0


def test_features_do_not_look_into_future() -> None:
    history = _history()
    index = 600
    assert features(history, index) == features(history[: index + 1], index)


def test_future_target_is_not_used_in_training() -> None:
    history = _history()
    modified = history[:-7] + tuple(
        Observation(point.day, point.close * 100) for point in history[-7:]
    )
    original = train_hybrid(history[:-7])
    changed = train_hybrid(modified[:-7])
    assert original == changed


def test_insufficient_history_is_rejected() -> None:
    with pytest.raises(ValueError, match="Insufficient"):
        train_hybrid(_history(400))
