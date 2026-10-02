from __future__ import annotations

import pytest
from scripts.challenger_v2_agent_contract import AgentTask, validate_agent_output


def _task(dataset_role: str = "development") -> AgentTask:
    return AgentTask(
        task_id="classical-1d-001",
        lane="classical_ml",
        horizon="1d",
        dataset_role=dataset_role,
        objective="build a validation-only challenger",
        parent_commit="abc123",
    )


def test_development_task_is_allowed() -> None:
    assert _task().manifest()["lane"] == "classical_ml"


@pytest.mark.parametrize(
    "dataset_role",
    ["evidence_v1_locked", "fresh_locked_oos", "prospective_holdout"],
)
def test_agent_cannot_access_confirmatory_data(dataset_role: str) -> None:
    with pytest.raises(ValueError, match="cannot access"):
        _task(dataset_role).validate()


def test_agent_cannot_self_promote() -> None:
    with pytest.raises(ValueError, match="cannot choose Champion"):
        validate_agent_output(
            _task(),
            {
                "task_id": "classical-1d-001",
                "parent_commit": "abc123",
                "champion": "xgboost",
            },
        )


def test_output_must_bind_to_parent_commit() -> None:
    with pytest.raises(ValueError, match="parent commit mismatch"):
        validate_agent_output(
            _task(),
            {"task_id": "classical-1d-001", "parent_commit": "wrong"},
        )
