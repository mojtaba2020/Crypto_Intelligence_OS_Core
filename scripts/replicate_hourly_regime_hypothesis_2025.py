"""Run the preregistered 2025 Bitstamp replication without replacing the 2023 primary."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from datetime import UTC
from pathlib import Path

from calendar_regime_block_bootstrap import calendar_regime_block_bootstrap
from confirm_hourly_regime_hypothesis import (
    BOOTSTRAP_METHOD,
    BOOTSTRAP_REPETITIONS,
    BOOTSTRAP_SEED,
    CALENDAR_BLOCK_LENGTH_DAYS,
    FEATURE,
    HORIZON_HOURS,
    LOSS,
    MIN_REGIME_SAMPLES,
    RIDGE_ALPHA,
    SCALING,
    STEP_HOURS,
    TARGET_REGIME,
    TRAIN_MIN_HOURS,
    _assert_independent_period,
    _assert_locked_walk_forward_design,
    _evaluate_preregistered_feature,
    _parse_utc,
    _validate_locked_preregistration,
)
from crypto_intelligence_os.adapters.market_data.bitstamp import INSTRUMENT_ID, SOURCE_ID
from crypto_intelligence_os.adapters.market_data.historical_archive import (
    HistoricalOHLCVArchive,
    canonical_bar_fingerprint,
    validate_hourly_continuity,
)
from hourly_regime_v1 import classify_regime

REPLICATION_START = "2025-01-01T00:00:00+00:00"
REPLICATION_END_EXCLUSIVE = "2026-01-01T00:00:00+00:00"
REPLICATION_LAST_OPEN = "2025-12-31T23:00:00+00:00"


def _validate_replication_lock(prereg: dict) -> None:
    _validate_locked_preregistration(prereg)
    period = prereg["confirmatory_data"].get("replication_period")
    if period != "2025-01-01T00:00:00Z/2025-12-31T23:00:00Z":
        raise ValueError("Replication period drifted from preregistered 2025")
    if prereg["acceptance_rule"].get("promotion_requires_replication") is not True:
        raise ValueError("Replication requirement drifted")


def _validate_replication_ingestion(report: dict, bars) -> str:
    fingerprint = canonical_bar_fingerprint(bars)
    expected = {
        "status": "BITSTAMP_LONG_HISTORY_INGESTED",
        "requested_start_utc": REPLICATION_START,
        "requested_end_utc": REPLICATION_END_EXCLUSIVE,
        "source_id": SOURCE_ID,
        "instrument_id": INSTRUMENT_ID,
        "timeframe": "1h",
        "expected_count": len(bars),
        "fetched_count": len(bars),
        "stored_count": len(bars),
        "first_open_utc": bars[0].open_time.isoformat(),
        "last_open_utc": bars[-1].open_time.isoformat(),
        "continuity": "PASS",
        "sqlite_integrity": "PASS",
        "canonical_data_sha256": fingerprint,
    }
    for key, value in expected.items():
        if report.get(key) != value:
            raise ValueError(f"Replication ingestion chain mismatch: {key}")
    if report.get("missing_count") != 0:
        raise ValueError("Replication ingestion chain mismatch: missing_count")
    return fingerprint


def run(
    database: Path,
    preregistration: Path,
    output: Path,
    ingestion_report: Path,
    runner_git_sha: str | None = None,
) -> dict:
    prereg_bytes = preregistration.read_bytes()
    prereg = json.loads(prereg_bytes.decode("utf-8"))
    prereg_sha = hashlib.sha256(prereg_bytes).hexdigest()
    _assert_locked_walk_forward_design()
    _validate_replication_lock(prereg)

    with HistoricalOHLCVArchive(database) as archive:
        archive.integrity_check()
        bars = archive.read(
            instrument_id=INSTRUMENT_ID,
            timeframe="1h",
            source_id=SOURCE_ID,
        )
    validate_hourly_continuity(bars)

    if bars[0].open_time.astimezone(UTC) != _parse_utc(REPLICATION_START):
        raise ValueError("Replication archive start must be exactly 2025-01-01T00:00Z")
    if bars[-1].open_time.astimezone(UTC) != _parse_utc(REPLICATION_LAST_OPEN):
        raise ValueError("Replication archive end must be exactly 2025-12-31T23:00Z")
    _assert_independent_period(
        bars[0].open_time,
        bars[-1].open_time,
        prereg["created_from_exploratory_dataset"]["period"],
    )

    report = json.loads(ingestion_report.read_text(encoding="utf-8"))
    fingerprint = _validate_replication_ingestion(report, bars)

    candles = [
        {
            "open": float(b.open),
            "high": float(b.high),
            "low": float(b.low),
            "close": float(b.close),
            "volume": float(b.volume),
        }
        for b in bars
    ]
    paired = _evaluate_preregistered_feature(candles)
    regimes = [classify_regime(candles, int(origin)) for origin in paired["origins"]]
    selected = [regime == TARGET_REGIME for regime in regimes]
    model = [float(x) for x, keep in zip(paired["model_losses"], selected, strict=True) if keep]
    baseline = [
        float(x) for x, keep in zip(paired["baseline_losses"], selected, strict=True) if keep
    ]
    hits = [int(x) for x, keep in zip(paired["direction_hits"], selected, strict=True) if keep]
    n = len(model)

    result = {
        "status": "PREREGISTERED_REPLICATION_RESULT_V1",
        "role": "REPLICATION_NOT_REPLACEMENT_PRIMARY",
        "promotion_authority": "NONE_WITHOUT_PRIMARY_PASS",
        "feature": FEATURE,
        "horizon_hours": HORIZON_HOURS,
        "regime": TARGET_REGIME,
        "validated_bar_count": len(bars),
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
        "continuity": "PASS",
        "sqlite_integrity": "PASS",
        "ingestion_chain_of_custody": "PASS",
        "canonical_data_sha256": fingerprint,
        "preregistration_sha256": prereg_sha,
        "runner_git_sha": runner_git_sha or "NOT_PROVIDED",
    }

    if n < MIN_REGIME_SAMPLES:
        result["decision"] = "REPLICATION_INSUFFICIENT_SAMPLES"
    else:
        model_mape = 100 * statistics.mean(model)
        baseline_mape = 100 * statistics.mean(baseline)
        gate = calendar_regime_block_bootstrap(
            [float(x) for x in paired["model_losses"]],
            [float(x) for x in paired["baseline_losses"]],
            selected,
            block_length=CALENDAR_BLOCK_LENGTH_DAYS,
            repetitions=BOOTSTRAP_REPETITIONS,
            seed=BOOTSTRAP_SEED,
        )
        supports = gate["gate"] == "PASS" and model_mape < baseline_mape
        result.update(
            {
                "model_mape_pct": model_mape,
                "persistence_mape_pct": baseline_mape,
                "mape_improvement_vs_persistence_pct": (
                    100 * (baseline_mape - model_mape) / baseline_mape if baseline_mape else 0.0
                ),
                "direction_accuracy_pct": 100 * sum(hits) / n,
                "statistical_gate": gate,
                "decision": (
                    "REPLICATION_SUPPORTS_HYPOTHESIS"
                    if supports
                    else "REPLICATION_DOES_NOT_SUPPORT_HYPOTHESIS"
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
    parser.add_argument("--ingestion-report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--runner-git-sha")
    args = parser.parse_args()
    print(
        json.dumps(
            run(
                args.database,
                args.preregistration,
                args.output,
                args.ingestion_report,
                args.runner_git_sha,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
