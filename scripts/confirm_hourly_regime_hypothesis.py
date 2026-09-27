#!/usr/bin/env python3
"""Run a preregistered confirmatory hourly-regime hypothesis on an independent archive."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from datetime import UTC, datetime, timedelta
from pathlib import Path

from calendar_regime_block_bootstrap import calendar_regime_block_bootstrap
from hourly_features_v2 import feature_names, feature_vector
from hourly_regime_v1 import classify_regime
from train_hourly_ridge_tournament import _ridge_fit
from crypto_intelligence_os.adapters.market_data.bitstamp import INSTRUMENT_ID, SOURCE_ID
from crypto_intelligence_os.adapters.market_data.historical_archive import (
    HistoricalOHLCVArchive,
    canonical_bar_fingerprint,
    validate_hourly_continuity,
)

FEATURE = "range_mean_6h"
HORIZON_HOURS = 12
TRAIN_MIN_HOURS = 720
STEP_HOURS = 24
RIDGE_ALPHA = 1.0
TARGET_REGIME = "down__low_vol"
MIN_REGIME_SAMPLES = 40
BOOTSTRAP_METHOD = "calendar_preserving_moving_block"
CALENDAR_BLOCK_LENGTH_DAYS = 7
BOOTSTRAP_REPETITIONS = 10_000
BOOTSTRAP_SEED = 20260927
LOSS = "absolute_percentage_error"
SCALING = "training_only_zscore_per_walk_forward_split"
EXPLORATORY_PERIOD = "2024-01-01T00:00:00Z/2024-12-31T23:00:00Z"
PRIMARY_PERIOD = "2023-01-01T00:00:00Z/2023-12-31T23:00:00Z"
PRIMARY_SOURCE = "Bitstamp"


def _assert_locked_walk_forward_design() -> None:
    if TRAIN_MIN_HOURS != 720:
        raise ValueError("Confirmatory train minimum drifted from locked 720 hours")
    if STEP_HOURS != 24:
        raise ValueError(
            "Confirmatory cadence drifted from one observation per calendar day"
        )
    if RIDGE_ALPHA != 1.0:
        raise ValueError("Confirmatory Ridge alpha drifted from locked value 1.0")


def _validate_locked_preregistration(prereg: dict) -> None:
    if prereg.get("status") != "PREREGISTERED_CONFIRMATORY_HYPOTHESIS":
        raise ValueError("Hypothesis is not in locked preregistered status")
    amendment = prereg["methodology_amendment_before_confirmatory_data_access"]
    if amendment.get("status") != "LOCKED_BEFORE_INDEPENDENT_TEST":
        raise ValueError("Methodology amendment is not locked before confirmation")

    hypothesis = prereg["hypothesis"]
    expected_hypothesis = {
        "feature": FEATURE,
        "horizon_hours": HORIZON_HOURS,
        "regime": TARGET_REGIME,
        "model": "ridge_alpha_1",
        "scaling": SCALING,
        "benchmark": "persistence",
        "loss": LOSS,
    }
    for key, expected in expected_hypothesis.items():
        if hypothesis.get(key) != expected:
            raise ValueError(
                f"Preregistration {key} does not match locked runner"
            )

    acceptance = prereg["acceptance_rule"]
    expected_acceptance = {
        "minimum_regime_samples": MIN_REGIME_SAMPLES,
        "bootstrap_method": BOOTSTRAP_METHOD,
        "calendar_block_length_days": CALENDAR_BLOCK_LENGTH_DAYS,
        "bootstrap_repetitions": BOOTSTRAP_REPETITIONS,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "must_beat_persistence": True,
        "independent_period_required": True,
        "promotion_after_single_pass": False,
        "promotion_requires_replication": True,
        "primary_requirement": "95% CI lower bound of paired loss improvement > 0",
    }
    for key, expected in expected_acceptance.items():
        if acceptance.get(key) != expected:
            raise ValueError(
                f"Preregistration acceptance rule {key} does not match "
                "locked runner"
            )

    exploratory = prereg["created_from_exploratory_dataset"]
    if exploratory.get("period") != EXPLORATORY_PERIOD:
        raise ValueError(
            "Exploratory period does not match locked 2024 dataset"
        )

    confirmatory = prereg["confirmatory_data"]
    if confirmatory.get("primary_period") != PRIMARY_PERIOD:
        raise ValueError(
            "Primary period does not match locked 2023 dataset"
        )
    if confirmatory.get("primary_source") != PRIMARY_SOURCE:
        raise ValueError(
            "Primary source does not match locked Bitstamp source"
        )
    if confirmatory.get("no_threshold_tuning_on_confirmatory_data") is not True:
        raise ValueError(
            "Preregistration must prohibit threshold tuning on confirmatory data"
        )


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
    exp_start, exp_last_open = _period(exploratory_period)
    # Stored research periods use first/last candle open times, both inclusive.
    exp_end_exclusive = exp_last_open + timedelta(hours=1)
    confirm_start = first_open.astimezone(UTC)
    confirm_end_exclusive = last_open.astimezone(UTC) + timedelta(hours=1)
    overlaps = (
        confirm_start < exp_end_exclusive
        and confirm_end_exclusive > exp_start
    )
    if overlaps:
        raise ValueError(
            "Confirmatory archive overlaps the exploratory period; "
            "refusing to reuse 2024 for confirmation"
        )


def _assert_exact_primary_period(
    first_open: datetime,
    last_open: datetime,
    primary_period: str,
) -> None:
    primary_start, primary_last_open = _period(primary_period)
    if (
        first_open.astimezone(UTC) != primary_start
        or last_open.astimezone(UTC) != primary_last_open
    ):
        raise ValueError(
            "Confirmatory archive must exactly match the preregistered "
            "primary 2023 period"
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
    _assert_locked_walk_forward_design()
    _validate_locked_preregistration(prereg)
    hypothesis = prereg["hypothesis"]
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

    primary_start, primary_last_open = _period(
        prereg["confirmatory_data"]["primary_period"]
    )
    _assert_exact_primary_period(
        bars[0].open_time,
        bars[-1].open_time,
        prereg["confirmatory_data"]["primary_period"],
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

    regimes = [
        classify_regime(candles, int(origin))
        for origin in paired["origins"]
    ]
    selected = [regime == target_regime for regime in regimes]
    selected_model = [
        float(loss)
        for loss, keep in zip(
            paired["model_losses"], selected, strict=True
        )
        if keep
    ]
    selected_baseline = [
        float(loss)
        for loss, keep in zip(
            paired["baseline_losses"], selected, strict=True
        )
        if keep
    ]
    selected_hits = [
        int(hit)
        for hit, keep in zip(
            paired["direction_hits"], selected, strict=True
        )
        if keep
    ]

    n = len(selected_model)
    min_samples = int(prereg["acceptance_rule"]["minimum_regime_samples"])
    result: dict = {
        "status": "PREREGISTERED_CONFIRMATORY_RESULT_V2",
        "feature": FEATURE,
        "horizon_hours": HORIZON_HOURS,
        "regime": target_regime,
        "data_source": SOURCE_ID,
        "instrument_id": INSTRUMENT_ID,
        "validated_bar_count": len(bars),
        "expected_primary_bar_count": int(
            (primary_last_open - primary_start).total_seconds() // 3600
        ) + 1,
        "first_open_utc": bars[0].open_time.isoformat(),
        "last_open_utc": bars[-1].open_time.isoformat(),
        "walk_forward_step_hours": STEP_HOURS,
        "train_min_hours": TRAIN_MIN_HOURS,
        "ridge_alpha": RIDGE_ALPHA,
        "loss": LOSS,
        "scaling": SCALING,
        "benchmark": "persistence",
        "minimum_regime_samples": MIN_REGIME_SAMPLES,
        "regime_samples": n,
        "bootstrap_method": BOOTSTRAP_METHOD,
        "calendar_block_length_days": CALENDAR_BLOCK_LENGTH_DAYS,
        "bootstrap_repetitions": BOOTSTRAP_REPETITIONS,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "independent_period_guard": "PASS",
        "continuity": "PASS",
        "sqlite_integrity": "PASS",
        "canonical_data_sha256": canonical_bar_fingerprint(bars),
    }

    if n < min_samples:
        result["decision"] = "INSUFFICIENT_SAMPLES"
    else:
        model_mape = 100 * statistics.mean(selected_model)
        baseline_mape = 100 * statistics.mean(selected_baseline)
        gate = calendar_regime_block_bootstrap(
            [float(x) for x in paired["model_losses"]],
            [float(x) for x in paired["baseline_losses"]],
            selected,
            block_length=int(
                prereg["acceptance_rule"]["calendar_block_length_days"]
            ),
            repetitions=int(
                prereg["acceptance_rule"]["bootstrap_repetitions"]
            ),
            seed=int(prereg["acceptance_rule"]["bootstrap_seed"]),
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
