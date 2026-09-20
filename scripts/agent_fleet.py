"""Bounded, fail-closed agent task queue. No model API or autonomous workers are connected.

Run: python -m scripts.agent_fleet --manifest .agent_fleet/pilot.json --dry-run
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROLE_COUNT = 100
ALLOWED_KINDS = {"data_audit", "model_research", "independent_evaluation", "ci_review"}
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def validate_manifest(manifest: dict) -> list[dict]:
    if manifest.get("schema_version") != 1:
        raise ValueError("schema_version must be 1")
    limit = manifest.get("max_active_workers")
    if type(limit) is not int or not 1 <= limit <= ROLE_COUNT:
        raise ValueError("max_active_workers must be 1..100")
    if manifest.get("mode") != "dry_run":
        raise ValueError("only dry_run is authorized; no remote agents are connected")
    tasks = manifest.get("tasks")
    if not isinstance(tasks, list) or len(tasks) > ROLE_COUNT:
        raise ValueError("tasks must be a list of at most 100")
    seen = set()
    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError("each task must be an object")
        tid, role, kind = task.get("id"), task.get("agent_id"), task.get("kind")
        if not isinstance(tid, str) or not SAFE_ID.fullmatch(tid) or tid in seen:
            raise ValueError("task IDs must be unique and safe")
        seen.add(tid)
        if (
            not isinstance(role, str)
            or not re.fullmatch(r"A[0-9]{3}", role)
            or not 1 <= int(role[1:]) <= 100
        ):
            raise ValueError("agent_id must be A001..A100")
        if kind not in ALLOWED_KINDS:
            raise ValueError("unknown task kind")
        deps = task.get("depends_on", [])
        if not isinstance(deps, list) or any(not isinstance(x, str) for x in deps):
            raise ValueError("depends_on must be a list of IDs")
        if task.get("requires_external_access", False) is not False:
            raise ValueError("external access is disabled in pilot")
    for task in tasks:
        if any(dep not in seen or dep == task["id"] for dep in task.get("depends_on", [])):
            raise ValueError("missing or self-referential dependency")
    return tasks


def plan(manifest: dict) -> dict:
    tasks = validate_manifest(manifest)
    pending = {t["id"]: t for t in tasks}
    done = set()
    waves = []
    while pending:
        ready = sorted(
            (t for t in pending.values() if set(t.get("depends_on", [])) <= done),
            key=lambda t: t["id"],
        )
        if not ready:
            raise ValueError("dependency cycle detected")
        wave = ready[: manifest["max_active_workers"]]
        waves.append([{"id": t["id"], "agent_id": t["agent_id"], "kind": t["kind"]} for t in wave])
        for task in wave:
            done.add(task["id"])
            del pending[task["id"]]
    return {
        "mode": "dry_run",
        "role_capacity": ROLE_COUNT,
        "active_workers": 0,
        "planned_waves": waves,
        "dispatched_tasks": 0,
        "external_calls": 0,
        "cost_usd": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true", required=True)
    args = parser.parse_args()
    print(json.dumps(plan(json.loads(args.manifest.read_text(encoding="utf-8"))), indent=2))


if __name__ == "__main__":
    main()
