"""Optional isolated REAL CatBoost smoke: skip if research dependency is absent.

No market-data ingestion, provider calls or model selection. This is a
synthetic repeatability/runtime check and never scientific confirmation.
"""

from __future__ import annotations

import math
import time

import pytest
from scripts import challenger_v3_catboost_exploratory as lane


def test_real_catboost_synthetic_replay_and_no_disk_files(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    catboost = pytest.importorskip("catboost")
    monkeypatch.chdir(tmp_path)
    x = [[float(math.sin(i / 3)), float(i % 7), float(i) / 100] for i in range(80)]
    y = [0.005 * math.cos(i / 9) for i in range(80)]
    estimates = []
    for _ in range(2):
        model = lane._new_estimator()
        assert isinstance(model, catboost.CatBoostRegressor)
        assert model.get_params()["random_seed"] == lane.SEED
        assert model.get_params()["thread_count"] == 1
        started = time.perf_counter()
        model.fit(x, y)
        elapsed = time.perf_counter() - started
        assert 0 < elapsed < 60  # a smoke-test safety cap, not a benchmark
        estimates.append(float(model.predict([[0.2, 4, 0.82]])[0]))
    assert estimates[0] == pytest.approx(estimates[1], abs=1e-12)
    assert list(tmp_path.iterdir()) == []  # no catboost_info or other model files
