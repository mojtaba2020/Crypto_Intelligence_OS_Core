"""Tests for Challenger V3 bounded local workers."""

from pathlib import Path

from scripts.challenger_v3_orchestrator import build_plan
from scripts.challenger_v3_workers import execute_task


def _first_task() -> dict:
    return build_plan()["waves"][0][0]


def test_worker_blocks_when_manifest_is_missing(tmp_path: Path) -> None:
    packet = execute_task(_first_task(), repo_root=tmp_path)
    assert packet["result"]["status"] == "blocked"
    assert packet["evidence"] == []
    assert packet["production_eligible"] is False
    assert packet["leakage_checks"]["fresh_oos_access"] is False


def test_worker_hashes_declared_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "artifacts" / "prepared" / "prepared_manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text('{"schema_version":1}\n', encoding="utf-8")
    packet = execute_task(_first_task(), repo_root=tmp_path)
    assert packet["result"]["status"] == "completed"
    assert len(packet["evidence"]) == 1
    item = packet["evidence"][0]
    assert item["path"] == "artifacts/prepared/prepared_manifest.json"
    assert len(item["sha256"]) == 64
    assert item["bytes"] == manifest.stat().st_size


def test_nonfirst_worker_requires_upstream_evidence(tmp_path: Path) -> None:
    task = build_plan()["waves"][1][0]
    packet = execute_task(task, repo_root=tmp_path)
    assert packet["result"]["status"] == "blocked"
    assert "completed data_manifest_audit evidence packet" in packet["missing_data"]


def test_feature_and_stats_workers_complete_after_data_packet(tmp_path: Path) -> None:
    manifest = tmp_path / "artifacts" / "prepared" / "prepared_manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text('{"schema_version":1}\n', encoding="utf-8")
    evidence_dir = tmp_path / "artifacts" / "v3-agent-evidence"
    evidence_dir.mkdir(parents=True)
    data_packet = execute_task(_first_task(), repo_root=tmp_path)
    import json
    (evidence_dir / "data_manifest_audit.json").write_text(
        json.dumps(data_packet), encoding="utf-8"
    )
    for task in build_plan()["waves"][1]:
        packet = execute_task(task, repo_root=tmp_path)
        assert packet["result"]["status"] == "completed"
        assert packet["evidence"][0]["upstream_task"] == "data_manifest_audit"
        assert packet["production_eligible"] is False
        assert packet["leakage_checks"]["fresh_oos_access"] is False


def test_model_agents_require_feature_packet(tmp_path: Path) -> None:
    for task in build_plan()["waves"][2]:
        packet = execute_task(task, repo_root=tmp_path)
        assert packet["result"]["status"] == "blocked"
        assert "completed point_in_time_feature_spec evidence packet" in packet["missing_data"]


def test_model_agents_complete_after_feature_packet(tmp_path: Path) -> None:
    import json
    evidence_dir = tmp_path / "artifacts" / "v3-agent-evidence"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "point_in_time_feature_spec.json").write_text(
        json.dumps({"result": {"status": "completed"}}), encoding="utf-8"
    )
    model_tasks = [t for t in build_plan()["waves"][2] if t["id"] in {"classical_candidate_spec", "neural_adapter_spec"}]
    assert len(model_tasks) == 2
    for task in model_tasks:
        packet = execute_task(task, repo_root=tmp_path)
        assert packet["result"]["status"] == "completed"
        assert packet["production_eligible"] is False
        assert packet["leakage_checks"]["fresh_oos_access"] is False
        assert packet["evidence"][0]["upstream_task"] == "point_in_time_feature_spec"


def test_classical_worker_spec_matches_implemented_target_and_safety(tmp_path: Path) -> None:
    import json

    evidence_dir = tmp_path / "artifacts" / "v3-agent-evidence"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "point_in_time_feature_spec.json").write_text(
        json.dumps({"result": {"status": "completed"}}), encoding="utf-8"
    )
    task = next(
        t for t in build_plan()["waves"][2] if t["id"] == "classical_candidate_spec"
    )
    packet = execute_task(task, repo_root=tmp_path)
    spec = packet["result"]["spec"]
    assert spec["target"] == "future_log_return_by_predeclared_horizon_reconstructed_to_price_for_APE"
    assert spec["implementation_source"] == "scripts/multitimeframe_tournament_v2.py"
    assert spec["selection"] == "development_validation_only_minimum_MAPE_then_declared_candidate_order_tie_break"
    assert "fresh_locked_oos" in spec["forbidden"]
    assert "production_promotion" in spec["forbidden"]
