"""Tests for the deterministic Challenger V3 orchestrator."""

from scripts.challenger_v3_orchestrator import AGENTS, build_plan


def test_v3_plan_has_eight_unique_agents() -> None:
    plan = build_plan()
    ids = [agent["agent_id"] for agent in plan["agents"]]
    assert len(AGENTS) == 8
    assert len(ids) == len(set(ids)) == 8


def test_v3_plan_is_fail_closed() -> None:
    plan = build_plan()
    assert plan["mode"] == "plan_only"
    for wave in plan["waves"]:
        for task in wave:
            assert task["scope"] == "development_validation_only"
            assert task["fresh_oos_access"] is False
            assert task["production_eligible"] is False


def test_v3_dependencies_are_ordered() -> None:
    plan = build_plan()
    wave_of = {
        task["id"]: index
        for index, wave in enumerate(plan["waves"])
        for task in wave
    }
    for wave in plan["waves"]:
        for task in wave:
            for dependency in task["depends_on"]:
                assert wave_of[dependency] < wave_of[task["id"]]


def test_v3_adversarial_review_precedes_readiness() -> None:
    plan = build_plan()
    ordered = [
        task["id"]
        for wave in plan["waves"]
        for task in wave
    ]
    assert ordered.index("leakage_adversarial_review") < ordered.index("selection_bias_challenge")
    assert ordered.index("selection_bias_challenge") < ordered.index("v3_readiness_packet")
