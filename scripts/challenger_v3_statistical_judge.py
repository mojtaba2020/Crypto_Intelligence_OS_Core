#!/usr/bin/env python3
"""Corrected development-only statistical diagnostics for Challenger V3.

The primary method is a deterministic studentized circular moving-block
bootstrap (CMBB) over chronological forecast-origin paired loss differences.
It never reads fresh/locked OOS and cannot authorize Freeze or promotion.
Stationary-bootstrap and HAC results are fixed sensitivity diagnostics only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
from collections.abc import Mapping, Sequence
from pathlib import Path

try:
    from .challenger_v3_nested_selection import purged_diagnostic_records, select_candidate
    from .multitimeframe_lab_v1 import SPECS
except ImportError:  # direct script execution with scripts/ on sys.path
    from challenger_v3_nested_selection import purged_diagnostic_records, select_candidate
    from multitimeframe_lab_v1 import SPECS

ALPHA = 0.05
BOOTSTRAP_REPS = 10000
SEED = 20261003
MIN_DIAGNOSTIC_ORIGINS = 20
MIN_EFFECTIVE_BLOCKS = 5.0
MAX_BLOCK_SAMPLE_RATIO = 0.25
MIN_VALID_BOOTSTRAP_FRACTION = 0.99
HYPOTHESIS_FAMILY_ID = "v3_nested_development_all_horizon_x_ablation_winners_cmbb_v1"


def _quantile(values: Sequence[float], probability: float) -> float:
    if not values or not 0.0 <= probability <= 1.0:
        raise ValueError("invalid empirical quantile")
    ordered = sorted(values)
    return ordered[max(0, math.ceil(probability * len(ordered)) - 1)]


def _canonical_rotation(values: Sequence[float]) -> list[float]:
    """Canonicalize the circle so seeded Monte Carlo is rotation invariant."""
    rows = list(values)
    return min((rows[i:] + rows[:i] for i in range(len(rows))), key=tuple)


def _hac_standard_error(values: Sequence[float], max_lag: int) -> float:
    """Bartlett-kernel long-run standard error used for studentization."""
    n = len(values)
    if n < 2:
        raise ValueError("at least two observations are required")
    mean = statistics.fmean(values)
    centered = [value - mean for value in values]
    lag = min(max_lag, n - 1)
    long_run_variance = statistics.fmean(value * value for value in centered)
    for offset in range(1, lag + 1):
        covariance = (
            sum(centered[index] * centered[index - offset] for index in range(offset, n)) / n
        )
        long_run_variance += 2.0 * (1.0 - offset / (lag + 1.0)) * covariance
    if not math.isfinite(long_run_variance) or long_run_variance <= 0.0:
        raise ValueError("non-positive studentizing long-run variance")
    return math.sqrt(long_run_variance / n)


def _validate_bootstrap_design(
    sample_count: int,
    block_origins: int,
    *,
    minimum_samples: int = MIN_DIAGNOSTIC_ORIGINS,
    minimum_effective_blocks: float = MIN_EFFECTIVE_BLOCKS,
    maximum_block_ratio: float = MAX_BLOCK_SAMPLE_RATIO,
) -> dict[str, float | int]:
    if sample_count < minimum_samples:
        raise ValueError(f"inadequate diagnostic sample size: {sample_count} < {minimum_samples}")
    if block_origins <= 0 or block_origins > sample_count:
        raise ValueError("block length in origins must be within the diagnostic sample")
    ratio = block_origins / sample_count
    effective_blocks = sample_count / block_origins
    if ratio > maximum_block_ratio:
        raise ValueError(f"excessive block/sample ratio: {ratio:.6f} > {maximum_block_ratio:.6f}")
    if effective_blocks < minimum_effective_blocks:
        raise ValueError(
            f"inadequate effective blocks: {effective_blocks:.6f} < {minimum_effective_blocks:.6f}"
        )
    return {
        "block_sample_ratio": ratio,
        "effective_nonoverlapping_blocks": effective_blocks,
        "eligible_circular_block_starts": sample_count,
    }


def _circular_sample(values: Sequence[float], block: int, rng: random.Random) -> list[float]:
    n = len(values)
    sample: list[float] = []
    while len(sample) < n:
        start = rng.randrange(n)
        sample.extend(values[(start + offset) % n] for offset in range(block))
    return sample[:n]


def _studentized_circular_mbb(
    diffs: Sequence[float],
    block_origins: int,
    seed: int,
    *,
    repetitions: int = BOOTSTRAP_REPS,
    minimum_samples: int = MIN_DIAGNOSTIC_ORIGINS,
    minimum_effective_blocks: float = MIN_EFFECTIVE_BLOCKS,
    maximum_block_ratio: float = MAX_BLOCK_SAMPLE_RATIO,
) -> dict[str, object]:
    """One-sided bootstrap-t inference using an equal-weight circular MBB."""
    values = [float(value) for value in diffs]
    if any(not math.isfinite(value) for value in values):
        raise ValueError("paired differences must be finite")
    if repetitions < 99:
        raise ValueError("at least 99 bootstrap repetitions are required")
    design = _validate_bootstrap_design(
        len(values),
        block_origins,
        minimum_samples=minimum_samples,
        minimum_effective_blocks=minimum_effective_blocks,
        maximum_block_ratio=maximum_block_ratio,
    )
    values = _canonical_rotation(values)
    observed = statistics.fmean(values)
    observed_se = _hac_standard_error(values, block_origins - 1)
    observed_t = observed / observed_se
    centered = [value - observed for value in values]
    rng = random.Random(seed)  # noqa: S311 -- deterministic statistical bootstrap
    bootstrap_t: list[float] = []
    null_means: list[float] = []
    invalid = 0
    for _ in range(repetitions):
        sample = _circular_sample(centered, block_origins, rng)
        sample_mean = statistics.fmean(sample)
        null_means.append(sample_mean)
        try:
            sample_se = _hac_standard_error(sample, block_origins - 1)
        except ValueError:
            invalid += 1
            continue
        bootstrap_t.append(sample_mean / sample_se)
    if len(bootstrap_t) < repetitions * MIN_VALID_BOOTSTRAP_FRACTION:
        raise ValueError("too many bootstrap replicates had invalid studentizing variance")
    p_value = (1 + sum(value >= observed_t for value in bootstrap_t)) / (len(bootstrap_t) + 1)
    upper_t = _quantile(bootstrap_t, 1.0 - ALPHA)
    lower_bound = observed - upper_t * observed_se
    return {
        "method": "studentized_circular_moving_block_bootstrap",
        "alternative": "mean_paired_improvement_gt_0",
        "raw_p_value": p_value,
        "one_sided_confidence_level": 1.0 - ALPHA,
        "one_sided_lower_confidence_bound": lower_bound,
        "observed_studentized_statistic": observed_t,
        "observed_hac_standard_error": observed_se,
        "bootstrap_studentized_quantile_95": upper_t,
        "bootstrap_repetitions_requested": repetitions,
        "bootstrap_repetitions_valid": len(bootstrap_t),
        "bootstrap_repetitions_invalid": invalid,
        "null_bootstrap_mean": statistics.fmean(null_means),
        "null_bootstrap_mean_monte_carlo_se": statistics.pstdev(null_means)
        / math.sqrt(repetitions),
        "p_value_monte_carlo_se": math.sqrt(p_value * (1.0 - p_value) / (len(bootstrap_t) + 1)),
        "block_length_origins": block_origins,
        **design,
    }


def _stationary_bootstrap_sensitivity(
    diffs: Sequence[float], block_origins: int, seed: int, repetitions: int = BOOTSTRAP_REPS
) -> dict[str, object]:
    """Predeclared sensitivity only; never substitutes for the primary CMBB."""
    values = _canonical_rotation([float(value) for value in diffs])
    observed = statistics.fmean(values)
    observed_se = _hac_standard_error(values, block_origins - 1)
    observed_t = observed / observed_se
    centered = [value - observed for value in values]
    rng = random.Random(seed)  # noqa: S311 -- deterministic statistical bootstrap
    statistics_: list[float] = []
    invalid = 0
    for _ in range(repetitions):
        index = rng.randrange(len(values))
        sample = []
        for _position in range(len(values)):
            sample.append(centered[index])
            index = (
                rng.randrange(len(values))
                if rng.random() < 1.0 / block_origins
                else (index + 1) % len(values)
            )
        try:
            statistics_.append(
                statistics.fmean(sample) / _hac_standard_error(sample, block_origins - 1)
            )
        except ValueError:
            invalid += 1
            continue
    if len(statistics_) < repetitions * MIN_VALID_BOOTSTRAP_FRACTION:
        raise ValueError("stationary-bootstrap sensitivity has inadequate valid replicates")
    p_value = (1 + sum(value >= observed_t for value in statistics_)) / (len(statistics_) + 1)
    upper_t = _quantile(statistics_, 1.0 - ALPHA)
    return {
        "method": "studentized_stationary_bootstrap_sensitivity_only",
        "mean_block_length_origins": block_origins,
        "raw_p_value": p_value,
        "one_sided_lower_confidence_bound": observed - upper_t * observed_se,
        "valid_repetitions": len(statistics_),
        "invalid_repetitions": invalid,
        "selection_rule": "never_replaces_primary_method",
    }


def _hac_sensitivity(diffs: Sequence[float], block_origins: int) -> dict[str, object]:
    values = [float(value) for value in diffs]
    mean = statistics.fmean(values)
    standard_error = _hac_standard_error(values, block_origins - 1)
    statistic = mean / standard_error
    p_value = 0.5 * math.erfc(statistic / math.sqrt(2.0))
    return {
        "method": "bartlett_hac_normal_sensitivity_only",
        "max_lag_origins": block_origins - 1,
        "standard_error": standard_error,
        "raw_p_value": p_value,
        "one_sided_lower_confidence_bound": mean - 1.6448536269514722 * standard_error,
        "selection_rule": "never_replaces_primary_method",
    }


def _contiguous_origin_deletion_sensitivity(
    diffs: Sequence[float], max_block_origins: int
) -> dict[str, object]:
    """Adversarially delete every contiguous origin block up to a fixed maximum."""
    values = [float(value) for value in diffs]
    if any(not math.isfinite(value) for value in values):
        raise ValueError("paired differences must be finite")
    if len(values) < 2:
        raise ValueError("at least two paired differences are required")
    if max_block_origins <= 0 or max_block_origins >= len(values):
        raise ValueError("deletion block maximum must leave at least one origin")

    minimum_remaining_mean = math.inf
    worst_start = -1
    worst_block = -1
    by_block: list[dict[str, object]] = []
    for block in range(1, max_block_origins + 1):
        local_minimum = math.inf
        local_start = -1
        for start in range(0, len(values) - block + 1):
            remaining = values[:start] + values[start + block :]
            remaining_mean = statistics.fmean(remaining)
            if remaining_mean < local_minimum:
                local_minimum = remaining_mean
                local_start = start
            if remaining_mean < minimum_remaining_mean:
                minimum_remaining_mean = remaining_mean
                worst_start = start
                worst_block = block
        by_block.append(
            {
                "deleted_block_origins": block,
                "minimum_remaining_mean_improvement": local_minimum,
                "worst_start_origin_position": local_start,
            }
        )

    return {
        "method": "contiguous_origin_deletion_sensitivity_only",
        "observed_mean_improvement": statistics.fmean(values),
        "maximum_deleted_block_origins": max_block_origins,
        "minimum_remaining_mean_improvement": minimum_remaining_mean,
        "worst_deleted_block_origins": worst_block,
        "worst_start_origin_position": worst_start,
        "positive_after_every_tested_deletion": minimum_remaining_mean > 0.0,
        "tested_block_lengths": by_block,
        "selection_rule": "never_replaces_primary_method",
    }


def _holm(rows: list[dict[str, object]]) -> None:
    ordered = sorted(
        rows,
        key=lambda row: (
            float(row["raw_p_value"]),
            str(row.get("horizon", "")),
            str(row.get("ablation", "")),
        ),
    )
    rejecting = True
    running_adjusted = 0.0
    family_size = len(ordered)
    for rank, row in enumerate(ordered, 1):
        raw = float(row["raw_p_value"])
        multiplier = family_size - rank + 1
        threshold = ALPHA / multiplier
        reject = rejecting and raw <= threshold
        running_adjusted = max(running_adjusted, min(1.0, multiplier * raw))
        row.update(
            {
                "hypothesis_family_id": HYPOTHESIS_FAMILY_ID,
                "hypothesis_family_size": family_size,
                "holm_rank": rank,
                "holm_threshold": threshold,
                "holm_adjusted_p_value": running_adjusted,
                "holm_reject": reject,
            }
        )
        if not reject:
            rejecting = False


def _validate_origin_records(
    records: Sequence[Mapping[str, object]], candidates: Sequence[str]
) -> None:
    if not records:
        raise ValueError("origin-level evidence must not be empty")
    indexes: list[int] = []
    timestamps: list[float] = []
    target_timestamps: list[float] = []
    required_candidates = set(candidates)
    for row in records:
        if "origin_index" not in row:
            raise ValueError("origin_index is required")
        indexes.append(int(row["origin_index"]))
        if row.get("origin_timestamp") is None or row.get("target_timestamp") is None:
            raise ValueError("origin_timestamp and target_timestamp are required")
        origin_timestamp = float(row["origin_timestamp"])
        target_timestamp = float(row["target_timestamp"])
        if not math.isfinite(origin_timestamp) or not math.isfinite(target_timestamp):
            raise ValueError("origin and target timestamps must be finite")
        if target_timestamp <= origin_timestamp:
            raise ValueError("target timestamp must be strictly after origin timestamp")
        timestamps.append(origin_timestamp)
        target_timestamps.append(target_timestamp)
        errors = row.get("candidate_errors")
        if not isinstance(errors, Mapping) or set(errors) != required_candidates:
            raise ValueError("candidate losses are incomplete or contain undeclared candidates")
        losses = [float(row["persistence_error"]), *(float(errors[name]) for name in candidates)]
        if any(not math.isfinite(value) or value < 0.0 for value in losses):
            raise ValueError("losses must be finite and non-negative")
    if indexes != sorted(indexes) or len(indexes) != len(set(indexes)):
        raise ValueError("origin indexes must be strictly chronological and unique")
    if timestamps != sorted(timestamps) or len(timestamps) != len(set(timestamps)):
        raise ValueError("origin timestamps must be strictly chronological and unique")
    if target_timestamps != sorted(target_timestamps):
        raise ValueError("target timestamps must be chronological")


def _validate_dataset_identity(value: object) -> str:
    identity = str(value)
    if len(identity) != 64 or any(
        character not in "0123456789abcdef" for character in identity.lower()
    ):
        raise ValueError("dataset_sha256 must be a 64-character hexadecimal digest")
    return identity.lower()


def _register_evidence_key(seen: set[tuple[str, str]], horizon: str, ablation: str) -> None:
    key = (horizon, ablation)
    if key in seen:
        raise ValueError(f"duplicate horizon x ablation evidence: {horizon} x {ablation}")
    seen.add(key)


def _diagnostic_metrics(
    records: Sequence[Mapping[str, object]], candidate: str
) -> dict[str, float | list[float]]:
    persistence = [float(record["persistence_error"]) for record in records]
    model = [float(record["candidate_errors"][candidate]) for record in records]  # type: ignore[index]
    differences = [base - challenger for base, challenger in zip(persistence, model, strict=True)]
    return {
        "candidate_mape": statistics.fmean(model),
        "persistence_mape": statistics.fmean(persistence),
        "mean_paired_improvement": statistics.fmean(differences),
        "win_fraction": statistics.fmean(value > 0.0 for value in differences),
        "differences": differences,
    }


def _evidence_digest(paths: Sequence[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    spec_by_label = {spec.label: spec for spec in SPECS}
    rows: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    evidence_paths = sorted(args.evidence_dir.glob("classical-development-*.json"))
    for path in evidence_paths:
        report = json.loads(path.read_text(encoding="utf-8"))
        for horizon, result in report.get("results", {}).items():
            if horizon not in spec_by_label:
                raise ValueError(f"undeclared horizon: {horizon}")
            spec = spec_by_label[horizon]
            dataset_identity = _validate_dataset_identity(result.get("dataset_sha256"))
            for ablation in result["ablation_selected_candidates"]:
                _register_evidence_key(seen, horizon, ablation)
                metrics = result["ablation_metrics"][ablation]
                candidates = tuple(metrics["candidates"].keys())
                paired = metrics["origin_level_paired_losses"]
                _validate_origin_records(paired, candidates)
                candidate, cut = select_candidate(paired, candidates)
                diagnostic_records, purged = purged_diagnostic_records(
                    paired,
                    cut,
                    horizon_bars=spec.horizon_bars,
                    evaluation_step_bars=spec.evaluation_step_bars,
                )
                diagnostic = _diagnostic_metrics(diagnostic_records, candidate)
                differences = diagnostic.pop("differences")
                seed = SEED + sum(
                    ord(character) for character in horizon + ":" + ablation + ":nested:cmbb"
                )
                inference_eligible = len(diagnostic_records) >= MIN_DIAGNOSTIC_ORIGINS
                if inference_eligible:
                    primary = _studentized_circular_mbb(
                        differences,
                        spec.bootstrap_block_origins,
                        seed,  # type: ignore[arg-type]
                    )
                    raw_p_value = primary["raw_p_value"]
                    lower_bound = primary["one_sided_lower_confidence_bound"]
                    sensitivity = {
                        "stationary_bootstrap": _stationary_bootstrap_sensitivity(
                            differences,
                            spec.bootstrap_block_origins,
                            seed + 1,  # type: ignore[arg-type]
                        ),
                        "hac": _hac_sensitivity(differences, spec.bootstrap_block_origins),  # type: ignore[arg-type]
                        "contiguous_origin_deletion": _contiguous_origin_deletion_sensitivity(
                            differences,
                            spec.bootstrap_block_origins,  # type: ignore[arg-type]
                        ),
                        "policy": "predeclared_sensitivity_only_never_select_by_favorability",
                    }
                else:
                    # Expected evidence insufficiency is a scientific non-result, not a
                    # workflow error. Keep the hypothesis in the Holm family with p=1
                    # so the predeclared minimum is never weakened to rescue a signal.
                    primary = {
                        "method": "not_evaluated_insufficient_diagnostic_origins",
                        "minimum_required": MIN_DIAGNOSTIC_ORIGINS,
                        "observed": len(diagnostic_records),
                    }
                    raw_p_value = 1.0
                    lower_bound = 0.0
                    sensitivity = {
                        "status": "not_evaluated_insufficient_diagnostic_origins",
                        "policy": "predeclared_sensitivity_only_never_select_by_favorability",
                    }
                rows.append(
                    {
                        "horizon": horizon,
                        "ablation": ablation,
                        "candidate": candidate,
                        "dataset_sha256": dataset_identity,
                        "selection_samples": cut,
                        "purged_origin_count": purged,
                        "diagnostic_sample_count": len(diagnostic_records),
                        "selection_method": "earlier_origins_only",
                        "diagnostic_method": "later_origins_after_target_maturity_purge",
                        **diagnostic,
                        "full_development_candidate_mape": metrics["candidates"][candidate]["mape"],
                        "full_development_persistence_mape": metrics["persistence_mape"],
                        "block_length_origins": spec.bootstrap_block_origins,
                        "approximate_block_duration_source_bars": (
                            spec.bootstrap_block_origins * spec.evaluation_step_bars
                        ),
                        "inference_eligible": inference_eligible,
                        "primary_inference": primary,
                        "raw_p_value": raw_p_value,
                        "one_sided_lower_confidence_bound_95": lower_bound,
                        "sensitivity_diagnostics": sensitivity,
                    }
                )

    if not rows:
        raise ValueError("no V3 development evidence was found")
    _holm(rows)
    for row in rows:
        row["diagnostic_pass"] = bool(
            float(row["mean_paired_improvement"]) > 0.0
            and float(row["one_sided_lower_confidence_bound_95"]) > 0.0
            and row["holm_reject"]
        )

    output = {
        "status": "CHALLENGER_V3_CORRECTED_NESTED_DEVELOPMENT_STATISTICAL_DIAGNOSTICS_ONLY",
        "method_version": "v3-studentized-circular-mbb-1",
        "confirmatory": False,
        "fresh_locked_oos_access": False,
        "v2_locked_oos_used_for_tuning": False,
        "freeze_authorized": False,
        "champion_authorized": False,
        "production_promotion": False,
        "historical_judge_results_policy": "preserved_separately_not_overwritten_or_reinterpreted",
        "input_evidence_sha256": _evidence_digest(evidence_paths),
        "primary_inference": {
            "method": "studentized_circular_moving_block_bootstrap",
            "paired_unit": "chronological_forecast_origin",
            "block_unit": "forecast_origins",
            "repetitions": BOOTSTRAP_REPS,
            "seed_base": SEED,
            "alpha": ALPHA,
            "minimum_diagnostic_origins": MIN_DIAGNOSTIC_ORIGINS,
            "minimum_effective_blocks": MIN_EFFECTIVE_BLOCKS,
            "maximum_block_sample_ratio": MAX_BLOCK_SAMPLE_RATIO,
        },
        "multiplicity": {
            "method": "holm_bonferroni",
            "alpha": ALPHA,
            "family_id": HYPOTHESIS_FAMILY_ID,
            "family_definition": (
                "all_evaluated_horizon_x_ablation_nested_winners_in_this_corrected_development_run"
            ),
            "family_size": len(rows),
        },
        "sensitivity_policy": (
            "stationary_bootstrap_and_HAC_are_predeclared_diagnostics_"
            "and_never_replace_primary_by_favorability"
        ),
        "results": rows,
        "interpretation": (
            "Development/validation diagnostics only; no Freeze, Champion, "
            "or production authorization."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
