"""Offline preflight tests for the separately gated Render BTC4h scheduler."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from scripts import btc4h_render_cron as render


def test_disabled_by_default_does_not_access_network_or_change_evidence(monkeypatch):
    monkeypatch.delenv("BTC4H_RENDER_ENABLED", raising=False)
    monkeypatch.delenv("BTC4H_GITHUB_WRITE_TOKEN", raising=False)
    monkeypatch.setattr(
        render, "command", lambda *args, **kwargs: pytest.fail("network accessed")
    )
    assert render.main() == 0


@pytest.mark.parametrize("minute", [8, 10, 12, 14])
def test_valid_issue_schedule(minute):
    assert render.phase_for(datetime(2026, 11, 15, 8, minute, tzinfo=UTC)) == "issue"


def test_score_schedule():
    assert render.phase_for(datetime(2026, 11, 15, 8, 20, tzinfo=UTC)) == "score"


@pytest.mark.parametrize("hour,minute", [(7, 8), (8, 7), (8, 16), (8, 59)])
def test_invalid_schedule_fails_closed(hour, minute):
    with pytest.raises(ValueError):
        render.phase_for(datetime(2026, 11, 15, hour, minute, tzinfo=UTC))


def test_competing_github_schedule_prevents_activation(tmp_path):
    workflow = tmp_path / ".github/workflows/btc4h_continuous.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("on:\n  workflow_dispatch:\n  schedule:\n    - cron: '8 * * * *'\n")
    with pytest.raises(RuntimeError, match="CUTOVER_GUARD"):
        render.ensure_no_competing_schedule(tmp_path)
    workflow.write_text("on:\n  workflow_dispatch:\n    inputs: {}\n")
    render.ensure_no_competing_schedule(tmp_path)


def test_missing_github_token_stops_before_network(monkeypatch, tmp_path):
    source = tmp_path
    fake_file = source / "scripts/btc4h_render_cron.py"
    fake_file.parent.mkdir(parents=True)
    fake_file.write_text("# synthetic\n")
    monkeypatch.setenv("BTC4H_RENDER_ENABLED", "true")
    monkeypatch.delenv("BTC4H_GITHUB_WRITE_TOKEN", raising=False)
    monkeypatch.setattr(render, "__file__", str(fake_file))
    monkeypatch.setattr(render, "ensure_no_competing_schedule", lambda root: None)
    monkeypatch.setattr(
        render, "command", lambda *args, **kwargs: pytest.fail("network accessed")
    )
    with pytest.raises(RuntimeError, match="BTC4H_GITHUB_WRITE_TOKEN missing"):
        render.main()
