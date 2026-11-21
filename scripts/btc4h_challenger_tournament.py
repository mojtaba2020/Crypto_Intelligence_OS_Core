"""Isolated, bounded, retrospective BTC four-hour challenger comparison.

No data fetching, training on locked OOS, scheduling, forecast publication,
orders, real-time predictions, or model promotion. Supplied as-of stamps are
UNVERIFIED source claims; this is NOT an independent prospective experiment.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

CANDIDATES = ("ridge", "elastic_net", "random_forest", "extra_trees", "boosting")
ALL_MODELS = ("persistence", *CANDIDATES)
MIN_TRAIN = 30
MAX_EVAL = 24
MAX_ROWS = 512
FEATURE_KEYS = ("momentum_4h", "volume_surprise", "momentum_times_volume")
FIELDS = frozenset(
    {
        "origin_utc",
        "issued_at_utc",
        "features_available_at_utc",
        "target_5m_close_utc",
        "target_first_observed_at_utc",
        "origin_reference_close_usd",
        "actual_close_usd",
        "features",
    }
)


@dataclass(frozen=True)
class Example:
    origin: datetime
    issued: datetime
    features_available: datetime
    target_close: datetime
    target_observed: datetime
    reference: float
    actual: float
    x: tuple[float, float, float]

    @property
    def y(self) -> float:
        return math.log(self.actual / self.reference)


def _stamp(value: Any) -> datetime:
    if not isinstance(value, str) or not (value.endswith("Z") or value.endswith("+00:00")):
        raise ValueError("timestamps must be explicit UTC ISO-8601 strings")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid UTC timestamp") from exc
    if result.tzinfo is None or result.utcoffset() != timedelta(0):
        raise ValueError("timestamps must be UTC")
    return result.astimezone(UTC)


def _positive(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("price must be numeric")
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError("price must be finite and positive")
    return result


def validate_rows(rows: list[dict[str, Any]]) -> list[Example]:
    if not isinstance(rows, list) or not 2 <= len(rows) <= MAX_ROWS:
        raise ValueError("requires 2..512 bounded input rows")
    parsed: list[Example] = []
    previous: datetime | None = None
    for item in rows:
        if not isinstance(item, dict) or set(item) != FIELDS:
            raise ValueError("unexpected or missing research row field")
        origin = _stamp(item["origin_utc"])
        issued = _stamp(item["issued_at_utc"])
        features_at = _stamp(item["features_available_at_utc"])
        close = _stamp(item["target_5m_close_utc"])
        target_seen = _stamp(item["target_first_observed_at_utc"])
        if previous is not None and origin <= previous:
            raise ValueError("origins must be strictly increasing without duplicates")
        previous = origin
        if origin.minute or origin.second or origin.microsecond or origin.hour % 4:
            raise ValueError("origin must be a canonical four-hour UTC slot")
        if not origin + timedelta(minutes=10) <= issued < origin + timedelta(minutes=15):
            raise ValueError("not an on-time four-hour issuance")
        if not origin <= features_at <= issued:
            raise ValueError("features were not available by issuance")
        if close != origin + timedelta(hours=4, minutes=15):
            raise ValueError("incorrect target bar close")
        if not 14_400 < (close - issued).total_seconds() <= 14_700:
            raise ValueError("incorrect forecast horizon")
        if target_seen < close:
            raise ValueError("outcome reported before target matured")
        reference = _positive(item["origin_reference_close_usd"])
        actual = _positive(item["actual_close_usd"])
        if abs(math.log(actual / reference)) >= 1.0:
            raise ValueError("implausible or unbounded label")
        features = item["features"]
        if not isinstance(features, dict) or set(features) != set(FEATURE_KEYS):
            raise ValueError("exact three feature keys required")
        values = tuple(features[key] for key in FEATURE_KEYS)
        if any(
            isinstance(val, bool)
            or not isinstance(val, (int, float))
            or not math.isfinite(float(val))
            or abs(float(val)) > 20
            for val in values
        ):
            raise ValueError("nonfinite or unbounded feature")
        m, v, z = (float(val) for val in values)
        if not math.isclose(z, m * v, rel_tol=1e-9, abs_tol=1e-12):
            raise ValueError("inconsistent interaction feature")
        parsed.append(
            Example(origin, issued, features_at, close, target_seen, reference, actual, (m, v, z))
        )
    return parsed


def _model(name: str) -> Any:
    """Lazy, optional scikit-learn research dependency. Never installs packages."""
    try:
        from sklearn.ensemble import (
            ExtraTreesRegressor,
            HistGradientBoostingRegressor,
            RandomForestRegressor,
        )
        from sklearn.linear_model import ElasticNet, Ridge
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:
        raise RuntimeError("offline research needs a preinstalled scikit-learn") from exc
    if name == "ridge":
        return make_pipeline(StandardScaler(), Ridge(alpha=100.0))
    if name == "elastic_net":
        return make_pipeline(
            StandardScaler(),
            ElasticNet(alpha=0.0001, l1_ratio=0.25, max_iter=2000, random_state=20261116),
        )
    if name == "random_forest":
        return RandomForestRegressor(
            n_estimators=48, max_depth=4, min_samples_leaf=5, random_state=20261116, n_jobs=1
        )
    if name == "extra_trees":
        return ExtraTreesRegressor(
            n_estimators=48, max_depth=4, min_samples_leaf=5, random_state=20261116, n_jobs=1
        )
    if name == "boosting":
        return HistGradientBoostingRegressor(
            learning_rate=0.05,
            max_iter=48,
            max_leaf_nodes=7,
            min_samples_leaf=10,
            early_stopping=False,
            random_state=20261116,
        )
    raise ValueError("unapproved model name")


def evaluate(rows: list[dict[str, Any]], *, model_factory: Any = None) -> dict[str, Any]:
    """Fixed expanding-window scoring; train on targets observed before issue."""
    records = validate_rows(rows)
    make_model = model_factory if model_factory is not None else _model
    errors: dict[str, list[float]] = {name: [] for name in ALL_MODELS}
    direction: dict[str, list[bool]] = {name: [] for name in CANDIDATES}
    evaluated: list[dict[str, Any]] = []
    cold_start = 0
    for index, current in enumerate(records):
        train = [
            past
            for past in records[:index]
            if past.target_observed <= current.issued and past.origin < current.origin
        ]
        if len(train) < MIN_TRAIN:
            cold_start += 1
            continue
        if len(evaluated) >= MAX_EVAL:
            break
        train_x = [list(row.x) for row in train]
        train_y = [row.y for row in train]
        predictions = {"persistence": 0.0}
        for name in CANDIDATES:
            estimator = make_model(name)
            estimator.fit(train_x, train_y)
            forecast = float(estimator.predict([list(current.x)])[0])
            if not math.isfinite(forecast) or abs(forecast) >= 0.5:
                raise ValueError("nonfinite or unbounded challenger prediction")
            predictions[name] = forecast
        for name, prediction in predictions.items():
            errors[name].append(abs(prediction - current.y))
            if name != "persistence" and prediction != 0 and current.y != 0:
                direction[name].append((prediction > 0) == (current.y > 0))
        evaluated.append(
            {
                "origin_utc": current.origin.isoformat().replace("+00:00", "Z"),
                "mature_training_rows": len(train),
            }
        )
    expected = int((records[-1].origin - records[0].origin) / timedelta(hours=4)) + 1
    details = {}
    for name in ALL_MODELS:
        values = errors[name]
        accuracy = direction.get(name, [])
        details[name] = {
            "mean_absolute_log_error": statistics.mean(values) if values else None,
            "delta_mae_vs_persistence": (
                statistics.mean(
                    baseline - err
                    for baseline, err in zip(errors["persistence"], values, strict=True)
                )
                if values
                else None
            ),
            "direction_correct": sum(accuracy),
            "direction_evaluable": len(accuracy),
            "direction_accuracy_conditional": (statistics.mean(accuracy) if accuracy else None),
            "correct_over_all_evaluated": (sum(accuracy) / len(values) if values else None),
        }
    return {
        "status": "DESCRIPTIVE_ONLY_NO_PROMOTION" if evaluated else "INSUFFICIENT_MATURE_DATA",
        "study": "RETROSPECTIVE_OFFLINE_NOT_LIVE",
        "first_party_timestamps_only": True,
        "no_model_winner_authorized": True,
        "input_rows": len(records),
        "expected_slots_between_bounds": expected,
        "missing_origin_slots": expected - len(records),
        "cold_start_rows": cold_start,
        "evaluation_cap": MAX_EVAL,
        "evaluated_rows": len(evaluated),
        "evaluated_origins": evaluated,
        "models": details,
        "note": "No live proof, independent as-of evidence, model promotion or trading.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    if args.input.stat().st_size > 1_000_000:
        parser.error("input too large")
    with args.input.open(encoding="utf-8") as stream:
        rows = [json.loads(line) for line in stream if line.strip()]
    print(json.dumps(evaluate(rows), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
