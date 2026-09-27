#!/usr/bin/env python3
"""Run a preregistered confirmatory hourly-regime hypothesis on an independent archive."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from datetime import UTC, datetime
from pathlib import Path

from hourly_features_v2 import feature_names, feature_vector
from hourly_regime_v1 import classify_regime
from paired_block_bootstrap import paired_block_bootstrap
from train_hourly_ridge_tournament import _ridge_fit
from crypto_intelligence_os.adapters.market_data.bitstamp import INSTRUMENT_ID, SOURCE_ID
from crypto_intelligence_os.adapters.market_data.historical_archive import (
    HistoricalOHLCVArchive,
    validate_hourly_continuity,
)

FEATURE = "range_mean_6h"
HORIZON_HOURS = 12
TRAIN_MIN_HOURS = 720
STEP_HOURS = 24
RIDGE_ALPHA = 1.0


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _period(value: str) -> tuple[datetime, datetime]:
    start, end = value.split("/", 1)
    return _parse_utc(start), _parse_utc(end)


def _assert_independent_period(
    first_open: datetime,
    last_open: datetime,
    exploratory_period: str,
) -> None:
    exp_start, exp_end = _period(exploratory_period)
    confirm_start = first_open.astimezone(UTC)
    confirm_end_exclusive = last_open.astimezone(UTC)
    # The archived last candle opens one hour before the exclusive dataset end.
    confirm_end_exclusive = confirm_end_exclusive.replace(
        minute=0, second=0, microsecond=0
    )
    confirm_end_exclusive = confirm_end_exclusive.timestamp() + 3600
    confirm_end_exclusive = datetime.fromtimestamp(confirm_end_exclusive, tz=UTC)
    overlaps = confirm_start < exp_end and confirm_end_exclusive > exp_start
    if overlaps:
        raise ValueError(
            "Confirmatory archive overlaps the exploratory period; "
            "refusing to reuse 2024 for confirmation"
        )


def _evaluate_preregistered_feature(
    candles: list[dict[str, float]],
) -> dict:
    names = feature_names()
    try:
        feature_index = names.index(FEATURE)
    except ValueError as exc:
        raise ValueError(f"Missing preregistered feature: {FEATURE}") from exc

    closes = [float(c["close"]) for c in candles]
    feature_cache = {
        origin: feature_vector(candles, origin)[feature_index]
        for origin in range(168, len(candles))
    }

    test_origins: list[int] = []
    model_losses: list[float] = []
    baseline_losses: list[float] = []
    direction_hits: list[int] = []

    for test_origin in range(
        TRAIN_MIN_HOURS,
        len(candles) - HORIZON_HOURS,
        STEP_HOURS,
    ):
        train_origins = list(range(168, test_origin - HORIZON_HOURS + 1))
        raw_train = [feature_cache[origin] for origin in train_origins]
        raw_test = feature_cache[test_origin]
        mean = statistics.mean(raw_train)
        std = statistics.pstdev(raw_train)
        scaled_train = [
            (value - mean) / std if std else 0.0
            for value in raw_train
        ]
        scaled_test = (raw_test - mean) / std if std else 0.0
        xs = [[1.0, value] for value in scaled_train]
        ys = [
            math.log(
                closes[origin + HORIZON_HOURS] / closes[origin]
            )
            for origin in train_origins
        ]
        beta = _ridge_fit(xs, ys, alpha=RIDGE_ALPHA)
        predicted_return = beta[0] + beta[1] * scaled_test

        current = closes[test_origin]
        actual = closes[test_origin + HORIZON_HOURS]
        predicted = current * math.exp(predicted_return)
        actual_return = math.log(actual / current)

        test_origins.append(test_origin)
        model_losses.append(abs(predicted - actual) / actual)
        baseline_losses.append(abs(current - actual) / actual)
        direction_hits.append(
            int((predicted_return >= 0) == (actual_return >= 0))
        )

    return {
        "origins": test_origins,
        "model_losses": model_losses,
        "baseline_losses": baseline_losses,
        "direction_hits": direction_hits,
    }


def run(database: Path, preregistration: Path, output: Path) -> dict:
    prereg = json.loads(preregistration.read_text(encoding="utf-8"))
    hypothesis = prereg["hypothesis"]
    if hypothesis["feature"] != FEATURE:
        raise ValueError("Preregistration feature does not match locked runner")
    if int(hypothesis["horizon_hours"]) != HORIZON_HOURS:
        raise ValueError("Preregistration horizon does not match locked runner")
    if hypothesis["model"] != "ridge_alpha_1":
        raise ValueError("Preregistration model does not match locked runner")
    if hypothesis["benchmark"] != "persistence":
        raise ValueError("Preregistration benchmark does not match locked runner")
    target_regime = str(hypothesis["regime"])

    with HistoricalOHLCVArchive(database) as archive:
        archive.integrity_check()
        bars = archive.read(
            instrument_id=INSTRUMENT_ID,
            timeframe="1h",
            source_id=SOURCE_ID,
        )
    validate_hourly_continuity(bars)
    if len(bars) < TRAIN_MIN_HOURS + HORIZON_HOURS + 1:
        raise ValueError("Independent archive is too short for confirmatory test")

    _assert_independent_period(
        bars[0].open_time,
        bars[-1].open_time,
        prereg["created_from_exploratory_dataset"]["period"],
    )

    candles = [
        {
            "open": float(bar.open),
            "high": float(bar.high),
            "low": float(bar.low),
            "close": float(bar.close),
            "volume": float(bar.volume),
        }
        for bar in bars
    ]
    paired = _evaluate_preregistered_feature(candles)

    selected_model: list[float] = []
    selected_baseline: list[float] = []
    selected_hits: list[int] = []
    for origin, model_loss, baseline_loss, hit in zip(
        paired["origins"],
        paired["model_losses"],
        paired["baseline_losses"],
        paired["direction_hits"],
        strict=True,
    ):
        if classify_regime(candles, int(origin)) == target_regime:
            selected_model.append(float(model_loss))
            selected_baseline.append(float(baseline_loss))
            selected_hits.append(int(hit))

    n = len(selected_model)
    min_samples = int(prereg["acceptance_rule"]["minimum_regime_samples"])
    result: dict = {
        "status": "PREREGISTERED_CONFIRMATORY_RESULT_V1",
        "feature": FEATURE,
        "horizon_hours": HORIZON_HOURS,
        "regime": target_regime,
        "data_source": SOURCE_ID,
        "instrument_id": INSTRUMENT_ID,
        "validated_bar_count": len(bars),
        "first_open_utc": bars[0].open_time.isoformat(),
        "last_open_utc": bars[-1].open_time.isoformat(),
        "walk_forward_step_hours": STEP_HOURS,
        "train_min_hours": TRAIN_MIN_HOURS,
        "regime_samples": n,
        "independent_period_guard": "PASS",
        "continuity": "PASS",
        "sqlite_integrity": "PASS",
    }

    if n < min_samples:
        result["decision"] = "INSUFFICIENT_SAMPLES"
    else:
        model_mape = 100 * statistics.mean(selected_model)
        baseline_mape = 100 * statistics.mean(selected_baseline)
        gate = paired_block_bootstrap(
            selected_model,
            selected_baseline,
            block_length=min(7, n),
            repetitions=int(
                prereg["acceptance_rule"]["paired_block_bootstrap_repetitions"]
            ),
        )
        result.update(
            {
                "model_mape_pct": model_mape,
                "persistence_mape_pct": baseline_mape,
                "mape_improvement_vs_persistence_pct": (
                    100 * (baseline_mape - model_mape) / baseline_mape
                    if baseline_mape
                    else 0.0
                ),
                "direction_accuracy_pct": 100 * sum(selected_hits) / n,
                "statistical_gate": gate,
                "decision": (
                    "CONFIRMATORY_PASS_PENDING_REPLICATION"
                    if gate["gate"] == "PASS" and model_mape < baseline_mape
                    else "CONFIRMATORY_FAIL"
                ),
            }
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--preregistration", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            run(args.database, args.preregistration, args.output),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
