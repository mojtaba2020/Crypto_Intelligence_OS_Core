"""Deterministic V3 research orchestrator: plans bounded agent work, no provider calls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

AGENTS = (
    ("V3-DATA", "data_provenance"),
    ("V3-FEATURE", "feature_research"),
    ("V3-CLASSICAL", "classical_modeling"),
    ("V3-NEURAL", "neural_time_series"),
    ("V3-STATS", "statistics"),
    ("V3-AUDIT", "leakage_audit"),
    ("V3-DEVIL", "devils_advocate"),
    ("V3-ORCH", "orchestrator"),
)

TASKS = (
    {"id": "data_manifest_audit", "agent": "V3-DATA", "depends_on": []},
    {
        "id": "point_in_time_feature_spec",
        "agent": "V3-FEATURE",
        "depends_on": ["data_manifest_audit"],
    },
    {
        "id": "classical_candidate_spec",
        "agent": "V3-CLASSICAL",
        "depends_on": ["point_in_time_feature_spec"],
    },
    {
        "id": "neural_adapter_spec",
        "agent": "V3-NEURAL",
        "depends_on": ["point_in_time_feature_spec"],
    },
    {"id": "statistical_gate_spec", "agent": "V3-STATS", "depends_on": ["data_manifest_audit"]},
    {
        "id": "leakage_adversarial_review",
        "agent": "V3-AUDIT",
        "depends_on": ["classical_candidate_spec", "neural_adapter_spec", "statistical_gate_spec"],
    },
    {
        "id": "selection_bias_challenge",
        "agent": "V3-DEVIL",
        "depends_on": ["leakage_adversarial_review"],
    },
    {"id": "v3_readiness_packet", "agent": "V3-ORCH", "depends_on": ["selection_bias_challenge"]},
)


def build_plan() -> dict:
    roles = dict(AGENTS)
    pending = {task["id"]: task for task in TASKS}
    completed: set[str] = set()
    waves: list[list[dict]] = []
    while pending:
        ready = sorted(
            (task for task in pending.values() if set(task["depends_on"]) <= completed),
            key=lambda task: task["id"],
        )
        if not ready:
            raise RuntimeError("V3 task graph contains a dependency cycle")
        wave = []
        for task in ready:
            wave.append(
                {
                    **task,
                    "role": roles[task["agent"]],
                    "scope": "development_validation_only",
                    "fresh_oos_access": False,
                    "production_eligible": False,
                }
            )
            completed.add(task["id"])
            del pending[task["id"]]
        waves.append(wave)
    return {
        "schema_version": 1,
        "program": "challenger_v3",
        "mode": "plan_only",
        "agents": [{"agent_id": a, "role": r} for a, r in AGENTS],
        "waves": waves,
        "locked_oos_policy": " ".join(
            (
                "V2 locked OOS is read-only historical evidence;",
                "never optimize V3 against it.",
            )
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    plan = build_plan()
    payload = json.dumps(plan, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
