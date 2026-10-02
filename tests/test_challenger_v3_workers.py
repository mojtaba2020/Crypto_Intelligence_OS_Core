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
    assert "upstream task evidence packet" in packet["missing_data"]
