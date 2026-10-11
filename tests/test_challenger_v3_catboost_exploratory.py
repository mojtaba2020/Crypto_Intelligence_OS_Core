"""Negative leakage/scope tests; no CatBoost dependency or live provider calls."""

from __future__ import annotations

import json
import math
from pathlib import Path
from types import SimpleNamespace

import pytest
from scripts import challenger_v3_catboost_exploratory as exploratory


def _candles(n: int = 114) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index in range(n):
        close = 100 * math.exp(0.001 * index + 0.004 * math.sin(index / 3))
        rows.append(
            {
                "timestamp": index * 604_800,
                "is_complete": True,
                "open": close * 0.998,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": 1000.0 + index,
            }
        )
    return rows


def _folds(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return exploratory.build_folds(
        rows, family="weekly", horizon=2, train_end=102, stride=3, max_folds=3
    )


def test_mature_labels_only_and_no_future_feature_injection() -> None:
    candles = _candles()
    folds = _folds(candles)
    assert [fold["origin"] for fold in folds] == [102, 105, 108]
    assert all(fold["last_train_target_index"] <= fold["origin"] for fold in folds)
    first = folds[0]
    candles[112]["close"] = float(candles[112]["close"]) * 1.1
    candles[112]["open"] = float(candles[112]["close"]) * 0.998
    candles[112]["high"] = float(candles[112]["close"]) * 1.01
    candles[112]["low"] = float(candles[112]["close"]) * 0.99
    # Rows after the first target cannot affect that fold's training or features.
    first_after = _folds(candles)[0]
    assert (first_after["x"], first_after["y"], first_after["forecast_x"]) == (
        first["x"], first["y"], first["forecast_x"]
    )


@pytest.mark.parametrize("corruption", ["incomplete", "gap", "nan"])
def test_missing_or_incomplete_candles_fail_closed(corruption: str) -> None:
    rows = _candles()
    if corruption == "incomplete":
        rows[65]["is_complete"] = False
    elif corruption == "gap":
        rows[65]["timestamp"] = int(rows[65]["timestamp"]) + 604_800
    else:
        rows[65]["close"] = float("nan")
    with pytest.raises(ValueError):
        _folds(rows)


def test_scope_inputs_refused_before_modeling(tmp_path: Path) -> None:
    path = tmp_path / "candidate.development.json"
    path.write_text(json.dumps({"scope": "fresh_locked_oos", "source": "no", "candles": []}))
    with pytest.raises(ValueError, match="Locked OOS"):
        exploratory.load_development_slice(path)
    path.write_text(
        json.dumps({"scope": exploratory.SCOPE, "source": "fixture", "candles": [], "locked": []})
    )
    with pytest.raises(ValueError, match="closed-schema"):
        exploratory.load_development_slice(path)
    blocked = tmp_path / "fresh_locked_oos.development.json"
    with pytest.raises(ValueError, match="forbidden"):
        exploratory.load_development_slice(blocked)


def test_catboost_missing_dependency_is_actionable(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(_name: str) -> None:
        raise ImportError("not installed")

    monkeypatch.setattr(exploratory.importlib, "import_module", missing)
    with pytest.raises(RuntimeError, match="Optional CatBoost is not installed"):
        exploratory._new_estimator()


def test_fold_isolation_seed_and_descriptive_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    constructed: list[object] = []
    seeds: list[int] = []

    class FakeCatBoost:
        def __init__(self, **kwargs: object):
            constructed.append(self)
            seeds.append(int(kwargs["random_seed"]))
            assert kwargs["allow_writing_files"] is False
            assert kwargs["thread_count"] == 1
            self.prediction = 0.0

        def fit(self, x: list[list[float]], y: list[float]) -> None:
            assert len(x) == len(y)
            self.prediction = sum(y) / len(y)

        def predict(self, x: list[list[float]]) -> list[float]:
            assert len(x) == 1
            return [self.prediction]

    monkeypatch.setattr(
        exploratory.importlib,
        "import_module",
        lambda _: SimpleNamespace(CatBoostRegressor=FakeCatBoost),
    )
    kw = {"family": "weekly", "horizon": 2, "train_end": 102, "stride": 3, "max_folds": 3}
    first = exploratory.evaluate_exploratory(_candles(), **kw)
    second = exploratory.evaluate_exploratory(_candles(), **kw)
    assert first == second
    assert first["status"] == "EXPLORATORY_ONLY"
    assert first["freeze"] == "NO_FREEZE"
    assert first["fresh_locked_oos_access"] is False
    assert first["n_origins"] == 3
    assert len(constructed) == 6
    assert len(set(map(id, constructed))) == 6
    assert seeds == [exploratory.SEED] * 6


def test_cost_bounds_and_immature_diagnostic_rejected() -> None:
    with pytest.raises(ValueError, match="budget"):
        exploratory.build_folds(
            _candles(), family="weekly", horizon=2,
            train_end=102, stride=1, max_folds=13
        )
    with pytest.raises(ValueError, match="insufficient"):
        exploratory.build_folds(
            _candles(), family="weekly", horizon=2,
            train_end=113, stride=1
        )
