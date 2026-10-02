#!/usr/bin/env python3
"""Fail-closed task contract for Challenger V2 research agents."""

from __future__ import annotations

from dataclasses import asdict, dataclass

ALLOWED_LANES = {
    "data_quality",
    "feature_research",
    "classical_ml",
    "neural_ts",
    "foundation_ts",
    "macro_cycle",
    "reproducibility_audit",
}
FORBIDDEN_DATASETS = {"evidence_v1_locked", "fresh_locked_oos", "prospective_holdout"}


@dataclass(frozen=True)
class AgentTask:
    task_id: str
    lane: str
    horizon: str
    dataset_role: str
    objective: str
    parent_commit: str

    def validate(self) -> None:
        if not all((self.task_id, self.horizon, self.objective, self.parent_commit)):
            raise ValueError("Agent task fields cannot be empty")
        if self.lane not in ALLOWED_LANES:
            raise ValueError(f"Unknown research lane: {self.lane}")
        if self.dataset_role in FORBIDDEN_DATASETS:
            raise ValueError("Research agents cannot access confirmatory/locked evidence")

    def manifest(self) -> dict[str, str]:
        self.validate()
        return asdict(self)


def validate_agent_output(task: AgentTask, output: dict[str, object]) -> None:
    """Require immutable task binding and prevent self-promotion claims."""
    task.validate()
    if output.get("task_id") != task.task_id:
        raise ValueError("Agent output is not bound to its declared task")
    if output.get("parent_commit") != task.parent_commit:
        raise ValueError("Agent output parent commit mismatch")
    if output.get("champion") is not None or output.get("production_authorized") is True:
        raise ValueError("Research agents cannot choose Champion or authorize production")
