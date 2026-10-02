"""Local fail-closed workers for Challenger V3 research tasks.

These workers produce auditable evidence packets from declared inputs. They do
not call model providers, access fresh OOS, authorize production, or trade.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.challenger_v3_orchestrator import build_plan


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def execute_task(task: dict, *, repo_root: Path) -> dict:
    """Execute one bounded local task and return a contract-shaped packet."""
    evidence: list[dict] = []
    missing: list[str] = []

    if task["id"] == "data_manifest_audit":
        manifest = repo_root / "artifacts" / "prepared" / "prepared_manifest.json"
        if manifest.is_file():
            evidence.append(
                {
                    "path": str(manifest.relative_to(repo_root)),
                    "sha256": _sha256(manifest),
                    "bytes": manifest.stat().st_size,
                }
            )
        else:
            missing.append("artifacts/prepared/prepared_manifest.json")
    else:
        missing.append("upstream task evidence packet")

    status = "completed" if not missing else "blocked"
    return {
        "schema_version": 1,
        "agent_id": task["agent"],
        "role": task["role"],
        "task_id": task["id"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": task["scope"],
        "hypothesis": "Task can be evaluated from declared development/validation evidence.",
        "method": "bounded_local_worker_v1",
        "result": {"status": status},
        "evidence": evidence,
        "counterevidence": [],
        "missing_data": missing,
        "leakage_checks": {
            "fresh_oos_access": False,
            "production_eligible": False,
        },
        "reproducibility": {"worker": "scripts/challenger_v3_workers.py"},
        "recommendation": "continue" if status == "completed" else "audit",
        "production_eligible": False,
    }


def run_ready_tasks(*, repo_root: Path, output_dir: Path) -> list[Path]:
    """Run only first-wave tasks; later waves require persisted upstream evidence."""
    plan = build_plan()
    first_wave = plan["waves"][0]
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for task in first_wave:
        packet = execute_task(task, repo_root=repo_root)
        path = output_dir / f'{task["id"]}.json'
        path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(path)
    return written
