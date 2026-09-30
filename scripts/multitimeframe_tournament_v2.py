#!/usr/bin/env python3
"""Challenger V2 classical-model development lane.

This module is deliberately separate from the frozen V1 evidence tournament.
It may be used for development/validation research only; it does not authorize
locked-OOS reuse, champion selection, or production promotion.
"""

from __future__ import annotations

from scripts import multitimeframe_tournament_v1 as v1

HORIZONS = v1.HORIZONS
CANDIDATES = (
    "ridge",
    "elastic_net",
    "extra_trees",
    "random_forest",
    "hist_gradient_boosting",
    "boosting",
)


def _fit_candidate(name: str, x: list[list[float]], y: list[float]):
    if name in {"ridge", "extra_trees", "boosting"}:
        return v1._fit_candidate(name, x, y)

    try:
        from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
        from sklearn.linear_model import ElasticNet
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:
        raise RuntimeError("scikit-learn is required for Challenger V2") from exc

    if name == "elastic_net":
        model = make_pipeline(
            StandardScaler(),
            ElasticNet(alpha=0.0001, l1_ratio=0.25, max_iter=5000, random_state=20260929),
        )
    elif name == "random_forest":
        model = RandomForestRegressor(
            n_estimators=200,
            min_samples_leaf=5,
            max_features=0.75,
            random_state=20260929,
            n_jobs=-1,
        )
    elif name == "hist_gradient_boosting":
        model = HistGradientBoostingRegressor(
            learning_rate=0.05,
            max_iter=150,
            max_leaf_nodes=15,
            l2_regularization=1.0,
            random_state=20260929,
        )
    else:
        raise ValueError(f"Unknown Challenger V2 candidate: {name}")

    model.fit(x, y)
    return model.predict


def evaluate(
    candles: list[dict[str, float]],
    family: str,
    horizon: int,
    min_train: int,
    step: int,
) -> dict[str, object]:
    """Run the V2 candidate set with V1 leakage-resistant walk-forward semantics."""
    original = v1.CANDIDATES
    original_fit = v1._fit_candidate
    try:
        v1.CANDIDATES = CANDIDATES
        v1._fit_candidate = _fit_candidate
        return v1.evaluate(candles, family, horizon, min_train, step)
    finally:
        v1.CANDIDATES = original
        v1._fit_candidate = original_fit
