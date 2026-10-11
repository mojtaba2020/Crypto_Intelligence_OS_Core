"""Fail-closed tests for development-only calendar-gap diagnostics."""

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import pytest
from scripts.challenger_v3_feature_ablation import ABLATIONS
from scripts.challenger_v3_model_curriculum import HORIZONS
from scripts.challenger_v3_origin_gap_audit import audit_origin_gaps
from scripts.multitimeframe_lab_v1 import SPECS


def _save(path: Path, packet: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(packet), encoding="utf-8")


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "development"
    statistical = tmp_path / "statistics.json"
    stats = []
    for spec in SPECS:
        if spec.label not in HORIZONS:
            continue
        horizon = spec.label
        bar = 86_400 if spec.family == "daily" else 7 * 86_400
        start = int(datetime(2020, 1, 6, tzinfo=UTC).timestamp())
        records = [
            {
                "origin_index": 100 + i * spec.evaluation_step_bars,
                "origin_timestamp": start + i * spec.evaluation_step_bars * bar,
                "target_timestamp": (
                    start + (i * spec.evaluation_step_bars + spec.horizon_bars) * bar
                ),
                "persistence_error": 0.12,
                "candidate_errors": {"elastic_net": 0.11},
            }
            for i in range(5)
        ]
        _save(
            root / f"classical-development-{horizon}.json",
            {
                "status": "CHALLENGER_V3_CLASSICAL_DEVELOPMENT_VALIDATION_ONLY",
                "fresh_locked_oos_access": False,
                "v2_locked_oos_used_for_tuning": False,
                "production_promotion": False,
                "results": {
                    horizon: {
                        "locked_test_access": False,
                        "data_role": "development_validation_only",
                        "ablation_metrics": {
                            name: {"origin_level_paired_losses": deepcopy(records)}
                            for name in ABLATIONS
                        },
                    }
                },
            },
        )
        for name in ABLATIONS:
            stats.append(
                {
                    "horizon": horizon,
                    "ablation": name,
                    "candidate": "elastic_net",
                    "selection_samples": 2,
                    "purged_origin_count": 0,
                    "diagnostic_sample_count": 3,
                    "mean_paired_improvement": 0.01,
                    "inference_eligible": False,
                    "holm_reject": False,
                }
            )
    _save(
        statistical,
        {
            "status": "CHALLENGER_V3_CORRECTED_NESTED_DEVELOPMENT_STATISTICAL_DIAGNOSTICS_ONLY",
            "fresh_locked_oos_access": False,
            "v2_locked_oos_used_for_tuning": False,
            "freeze_authorized": False,
            "confirmatory": False,
            "results": stats,
        },
    )
    return root, statistical


def test_full_family_and_no_freeze(tmp_path):
    root, stats = _fixture(tmp_path)
    report = audit_origin_gaps(root, stats)
    assert report["hypothesis_count"] == 24
    assert len(report["horizons"]) == 6
    assert report["independent_confirmation"] is False
    assert report["freeze_authorized"] is False


def test_large_calendar_gap_reported_without_filling_missing_origins(tmp_path):
    root, stats = _fixture(tmp_path)
    path = root / "classical-development-1w.json"
    packet = json.loads(path.read_text())
    for ablation in ABLATIONS:
        records = packet["results"]["1w"]["ablation_metrics"][ablation][
            "origin_level_paired_losses"
        ]
        for i in range(2, 5):
            records[i]["origin_index"] += 40
            records[i]["origin_timestamp"] += 40 * 7 * 86_400
            records[i]["target_timestamp"] += 40 * 7 * 86_400
    _save(path, packet)
    report = audit_origin_gaps(root, stats)
    weekly = next(row for row in report["horizons"] if row["horizon"] == "1w")
    assert weekly["missing_scheduled_origin_slots"] == 10
    assert len(weekly["calendar_gaps"]) == 1


def test_reject_locked_test_access(tmp_path):
    root, stats = _fixture(tmp_path)
    path = root / "classical-development-1w.json"
    data = json.loads(path.read_text())
    data["results"]["1w"]["locked_test_access"] = True
    _save(path, data)
    with pytest.raises(ValueError, match="locked outcomes"):
        audit_origin_gaps(root, stats)


def test_reject_mismatched_ablation_calendar(tmp_path):
    root, stats = _fixture(tmp_path)
    path = root / "classical-development-1w.json"
    data = json.loads(path.read_text())
    data["results"]["1w"]["ablation_metrics"][ABLATIONS[1]][
        "origin_level_paired_losses"
    ][0]["origin_timestamp"] += 86_400
    _save(path, data)
    with pytest.raises(ValueError, match="inconsistent ablation"):
        audit_origin_gaps(root, stats)


def test_reject_mean_tampering(tmp_path):
    root, stats = _fixture(tmp_path)
    data = json.loads(stats.read_text())
    data["results"][0]["mean_paired_improvement"] = 999
    _save(stats, data)
    with pytest.raises(ValueError, match="reconstructed diagnostic mean"):
        audit_origin_gaps(root, stats)


def test_reject_statistical_locked_access(tmp_path):
    root, stats = _fixture(tmp_path)
    data = json.loads(stats.read_text())
    data["fresh_locked_oos_access"] = True
    _save(stats, data)
    with pytest.raises(ValueError, match="invalid development-only"):
        audit_origin_gaps(root, stats)
