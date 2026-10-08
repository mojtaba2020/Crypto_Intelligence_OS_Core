from __future__ import annotations

import math
import random
import statistics

import pytest
from scripts.challenger_v3_statistical_judge import (
    _contiguous_origin_deletion_sensitivity,
    _hac_sensitivity,
    _holm,
    _register_evidence_key,
    _stationary_bootstrap_sensitivity,
    _studentized_circular_mbb,
    _validate_bootstrap_design,
    _validate_dataset_identity,
    _validate_origin_records,
)


def _infer(values, *, block=2, seed=20261003, repetitions=1999):
    return _studentized_circular_mbb(
        values,
        block,
        seed,
        repetitions=repetitions,
        minimum_samples=4,
        minimum_effective_blocks=2,
        maximum_block_ratio=0.5,
    )


def test_four_point_non_circular_counterexample_is_coherent_after_correction() -> None:
    # The old judge returned p~=0.33 and percentile CI [0.5, 2.0]. Under
    # studentization this tiny sample also produces too many zero-variance
    # replicates, so the corrected judge must fail closed rather than fabricate
    # finite statistics for them.
    with pytest.raises(ValueError, match="invalid studentizing variance"):
        _infer([-2.0, 3.0, 1.0, 1.0], block=2)


def test_circular_null_is_centered_to_monte_carlo_tolerance() -> None:
    result = _infer([-2.0, 3.0, 1.0, 1.0] * 5, block=2, repetitions=9999)
    tolerance = 5 * result["null_bootstrap_mean_monte_carlo_se"]
    assert abs(result["null_bootstrap_mean"]) <= tolerance
    assert result["bootstrap_repetitions_valid"] + result["bootstrap_repetitions_invalid"] == 9999


def test_stationary_bootstrap_fails_closed_on_too_many_invalid_replicates() -> None:
    with pytest.raises(ValueError, match="inadequate valid replicates"):
        _stationary_bootstrap_sensitivity(
            [-2.0, 3.0, 1.0, 1.0], block_origins=2, seed=20261003, repetitions=1999
        )


def test_circular_shift_invariance_and_deterministic_reproducibility() -> None:
    values = [-0.4, 0.1, 0.6, -0.2, 0.8, 0.3, -0.1, 0.5]
    first = _infer(values, block=2, seed=7)
    shifted = _infer(values[3:] + values[:3], block=2, seed=7)
    assert first == shifted
    assert first == _infer(values, block=2, seed=7)


def test_ci_and_p_value_are_coherent_for_edge_heavy_sequence() -> None:
    values = [-0.1] * 8 + [1.0] * 19 + [-0.1] * 8
    result = _studentized_circular_mbb(values, 4, 91, repetitions=3999)
    if result["one_sided_lower_confidence_bound"] > 0.0:
        assert result["raw_p_value"] <= 0.05


@pytest.mark.parametrize(
    "sample_count,block,message",
    [(19, 1, "sample size"), (20, 6, "block/sample ratio"), (20, 5, "effective blocks")],
)
def test_bootstrap_design_fails_closed(sample_count, block, message) -> None:
    with pytest.raises(ValueError, match=message):
        _validate_bootstrap_design(sample_count, block)


def test_holm_reports_complete_explicit_family_metadata() -> None:
    rows = [
        {"horizon": "1d", "ablation": "a", "raw_p_value": 0.001},
        {"horizon": "2d", "ablation": "a", "raw_p_value": 0.03},
        {"horizon": "3d", "ablation": "a", "raw_p_value": 0.04},
    ]
    _holm(rows)
    ordered = sorted(rows, key=lambda row: row["holm_rank"])
    assert [row["holm_reject"] for row in ordered] == [True, False, False]
    assert [row["hypothesis_family_size"] for row in rows] == [3, 3, 3]
    assert all(row["hypothesis_family_id"] for row in rows)
    assert all("holm_adjusted_p_value" in row for row in rows)
    assert ordered[0]["holm_threshold"] == pytest.approx(0.05 / 3)


def _records(indexes=(0, 1), timestamps=(10, 20)):
    return [
        {
            "origin_index": index,
            "origin_timestamp": timestamp,
            "target_timestamp": timestamp + 5,
            "persistence_error": 0.2,
            "candidate_errors": {"a": 0.1, "b": 0.15},
        }
        for index, timestamp in zip(indexes, timestamps, strict=True)
    ]


def test_origin_validation_rejects_duplicate_and_nonordered_origins() -> None:
    with pytest.raises(ValueError, match="indexes"):
        _validate_origin_records(_records((1, 1)), ("a", "b"))
    with pytest.raises(ValueError, match="indexes"):
        _validate_origin_records(_records((2, 1)), ("a", "b"))
    with pytest.raises(ValueError, match="timestamps"):
        _validate_origin_records(_records((1, 2), (20, 10)), ("a", "b"))


def test_origin_validation_requires_exact_target_timestamp_metadata() -> None:
    rows = _records()
    rows[0].pop("target_timestamp")
    with pytest.raises(ValueError, match="target_timestamp"):
        _validate_origin_records(rows, ("a", "b"))
    rows = _records()
    rows[0]["target_timestamp"] = rows[0]["origin_timestamp"]
    with pytest.raises(ValueError, match="strictly after"):
        _validate_origin_records(rows, ("a", "b"))


def test_origin_validation_rejects_incomplete_or_nonfinite_losses() -> None:
    rows = _records()
    rows[0]["candidate_errors"].pop("b")
    with pytest.raises(ValueError, match="incomplete"):
        _validate_origin_records(rows, ("a", "b"))


def test_dataset_identity_and_duplicate_evidence_fail_closed() -> None:
    assert _validate_dataset_identity("a" * 64) == "a" * 64
    with pytest.raises(ValueError, match="dataset_sha256"):
        _validate_dataset_identity("not-a-digest")
    seen = set()
    _register_evidence_key(seen, "2d", "state_v31_delta")
    with pytest.raises(ValueError, match="duplicate"):
        _register_evidence_key(seen, "2d", "state_v31_delta")
    rows = _records()
    rows[0]["candidate_errors"]["a"] = math.inf
    with pytest.raises(ValueError, match="finite"):
        _validate_origin_records(rows, ("a", "b"))


def test_contiguous_origin_deletion_finds_worst_case_block() -> None:
    values = [0.02] * 12 + [-0.15, -0.15] + [0.02] * 12
    result = _contiguous_origin_deletion_sensitivity(values, 2)
    assert result["maximum_deleted_block_origins"] == 2
    assert result["selection_rule"] == "never_replaces_primary_method"
    assert len(result["tested_block_lengths"]) == 2
    assert result["minimum_remaining_mean_improvement"] < statistics.fmean(values)
    assert result["worst_deleted_block_origins"] == 2


def test_contiguous_origin_deletion_can_disqualify_fragile_positive_mean() -> None:
    values = [-0.01] * 20 + [0.5]
    result = _contiguous_origin_deletion_sensitivity(values, 1)
    assert statistics.fmean(values) > 0.0
    assert result["minimum_remaining_mean_improvement"] < 0.0
    assert result["positive_after_every_tested_deletion"] is False


def test_contiguous_origin_deletion_fails_closed_on_invalid_block() -> None:
    with pytest.raises(ValueError, match="leave at least one"):
        _contiguous_origin_deletion_sensitivity([0.1, 0.2], 2)


def test_sensitivity_methods_are_permanently_labelled_nonselective() -> None:
    values = [0.01 * math.sin(i) + 0.001 for i in range(30)]
    stationary = _stationary_bootstrap_sensitivity(values, 2, 5, repetitions=499)
    hac = _hac_sensitivity(values, 2)
    assert stationary["selection_rule"] == "never_replaces_primary_method"
    assert hac["selection_rule"] == "never_replaces_primary_method"
    assert "sensitivity_only" in stationary["method"]
    assert "sensitivity_only" in hac["method"]
    assert stationary["valid_repetitions"] + stationary["invalid_repetitions"] == 499


def _synthetic_process(kind: str, seed: int, n: int = 80) -> list[float]:
    rng = random.Random(seed)  # noqa: S311 -- deterministic calibration simulation
    if kind == "iid":
        return [rng.gauss(0.0, 1.0) for _ in range(n)]
    if kind == "heavy_tailed":
        return [rng.gauss(0.0, 1.0) / max(0.15, rng.random()) for _ in range(n)]
    if kind == "ar1":
        out = [rng.gauss(0.0, 1.0)]
        for _ in range(1, n):
            out.append(0.6 * out[-1] + rng.gauss(0.0, 0.8))
        return out
    if kind == "ma_overlap":
        innovations = [rng.gauss(0.0, 1.0) for _ in range(n + 2)]
        return [sum(innovations[i : i + 3]) / 3 for i in range(n)]
    if kind == "heteroskedastic":
        return [rng.gauss(0.0, 0.3 + 1.4 * (i / n)) for i in range(n)]
    if kind == "regime_shift":
        return [rng.gauss(-0.35 if i < n // 2 else 0.35, 1.0) for i in range(n)]
    raise AssertionError(kind)


@pytest.mark.parametrize(
    "kind", ["iid", "heavy_tailed", "ar1", "ma_overlap", "heteroskedastic", "regime_shift"]
)
def test_simulation_calibration_diagnostics_are_finite_and_coherent(kind: str) -> None:
    # These fixed synthetic regimes are calibration diagnostics, never tuning
    # inputs. They verify execution and inversion coherence across common loss
    # processes rather than asserting a favorable statistical outcome.
    result = _studentized_circular_mbb(
        _synthetic_process(kind, 100 + len(kind)), 4, 200 + len(kind), repetitions=999
    )
    assert 0.0 <= result["raw_p_value"] <= 1.0
    assert math.isfinite(result["one_sided_lower_confidence_bound"])
    assert math.isfinite(result["null_bootstrap_mean"])
    if result["one_sided_lower_confidence_bound"] > 0.0:
        assert result["raw_p_value"] <= 0.05 + 1 / 1000
