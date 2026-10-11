"""Closed and affordable scientific agent wave guards."""

from pathlib import Path

import pytest
from scripts.challenger_v3_wave2_bounded import (
    MAX_OUTPUT_TOKENS,
    MAX_PROMPT_BYTES,
    MODEL,
    ROLES,
    maximum_usd,
    preflight,
)


def test_cost_ceiling():
    assert MAX_OUTPUT_TOKENS == 2400
    assert len(ROLES) * maximum_usd(MAX_PROMPT_BYTES) < 0.30


@pytest.mark.parametrize("task_id", tuple(ROLES))
def test_pinned_preflight_without_paid_call(monkeypatch, task_id):
    monkeypatch.setenv("OPENAI_MODEL", MODEL)
    root = Path(__file__).resolve().parents[1]
    paths = preflight(task_id, root)
    assert all(path.exists() for path in paths)


def test_no_model_switch(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "other")
    root = Path(__file__).resolve().parents[1]
    with pytest.raises(ValueError, match="unapproved"):
        preflight("STATS-02", root)


def test_no_unapproved_job(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", MODEL)
    with pytest.raises(ValueError, match="closed reviewer"):
        preflight("TRADER-02", Path(__file__).resolve().parents[1])


def test_invalid_byte_count():
    with pytest.raises(ValueError):
        maximum_usd(-1)
    with pytest.raises(ValueError):
        maximum_usd(True)
