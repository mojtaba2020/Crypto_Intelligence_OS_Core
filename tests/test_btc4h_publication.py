"""Offline Git-publication integration: first publish, then score, never rewrite.

Uses a temporary local bare Git remote. No GitHub API, market data, orders or
real publication is triggered during this test.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

GIT = shutil.which("git")
BASH = shutil.which("bash")
if GIT is None or BASH is None:
    pytest.skip("requires local Git and Bash executables", allow_module_level=True)

SCRIPT = Path(__file__).resolve().parents[1] / ".github/scripts/publish_btc4h_shadow.sh"
DATA_REF = "origin/data/btc4h-shadow-forward"


def _git(directory: Path, *args: str) -> str:
    return subprocess.run(  # noqa: S603 -- static local test fixture commands
        [GIT, "-C", str(directory), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _repo(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    bare = tmp_path / "upstream.git"
    project = tmp_path / "project"
    subprocess.run(  # noqa: S603 -- local fake Git repository only
        [GIT, "init", "--bare", str(bare)],
        check=True,
        capture_output=True,
    )
    subprocess.run(  # noqa: S603 -- static local test fixture commands
        [GIT, "init", "-b", "main", str(project)],
        check=True,
        capture_output=True,
    )
    _git(project, "config", "user.name", "Research Tester")
    _git(project, "config", "user.email", "tester@example.invalid")
    (project / "README.md").write_text("research branch must stay unchanged\n", encoding="utf-8")
    (project / "research").mkdir()
    _git(project, "add", "README.md")
    _git(project, "commit", "-m", "Create local fake engine checkout")
    _git(project, "remote", "add", "origin", str(bare))
    _git(project, "push", "origin", "main")
    env = dict(os.environ)
    env.update(
        {
            "GITHUB_WORKSPACE": str(project),
            "RUNNER_TEMP": str(tmp_path),
            "GITHUB_RUN_ID": "123456",
            "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
        }
    )
    return project, env


def _publish(project: Path, env: dict[str, str], phase: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 -- static local test fixture commands
        [BASH, str(SCRIPT), phase],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _remote_file(project: Path, path: str) -> str:
    _git(
        project,
        "fetch",
        "origin",
        "refs/heads/data/btc4h-shadow-forward:refs/remotes/origin/data/btc4h-shadow-forward",
    )
    return _git(project, "show", f"{DATA_REF}:research/{path}")


def test_anchor_is_saved_first_then_forecast_before_any_score(tmp_path):
    project, env = _repo(tmp_path)
    research = project / "research"
    main_before = _git(project, "rev-parse", "HEAD")
    anchor = "2026-11-08T12:00:00Z"
    (research / "btc4h_study_start_utc.txt").write_text(anchor + "\n", encoding="utf-8")

    first = _publish(project, env, "anchor")
    assert first.returncode == 0, first.stderr
    assert _remote_file(project, "btc4h_study_start_utc.txt") == anchor
    assert _git(project, "rev-parse", "HEAD") == main_before
    assert _git(project, "branch", "--show-current") == "main"

    forecast = {"origin_utc": anchor, "price_forecasts_usd": {"persistence": 65000}}
    forecast_line = json.dumps(forecast) + "\n"
    (research / "btc4h_shadow_forecasts.jsonl").write_text(forecast_line, encoding="utf-8")
    second = _publish(project, env, "issue")
    assert second.returncode == 0, second.stderr
    assert json.loads(_remote_file(project, "btc4h_shadow_forecasts.jsonl")) == forecast
    assert not (research / "btc4h_shadow_scores.jsonl").exists()
    assert _git(project, "rev-parse", "HEAD") == main_before

    # Publication receipt is an independently committed append-only phase.
    receipt = {"origin_utc": anchor, "remote_issue_commit_sha": "c" * 40}
    (research / "btc4h_shadow_publication_receipts.jsonl").write_text(
        json.dumps(receipt) + "\n", encoding="utf-8"
    )
    confirmed = _publish(project, env, "receipt")
    assert confirmed.returncode == 0, confirmed.stderr
    assert json.loads(_remote_file(project, "btc4h_shadow_publication_receipts.jsonl")) == receipt

    # A downstream scoring failure cannot erase the previously pushed issue.
    (research / "btc4h_shadow_scores.jsonl").write_text("invalid json\n", encoding="utf-8")
    corrupted = _publish(project, env, "score")
    assert corrupted.returncode != 0
    assert "invalid JSONL" in corrupted.stderr
    assert json.loads(_remote_file(project, "btc4h_shadow_forecasts.jsonl")) == forecast

    score = {"origin_utc": anchor, "absolute_log_price_errors": {"persistence": 0.005}}
    (research / "btc4h_shadow_scores.jsonl").write_text(json.dumps(score) + "\n", encoding="utf-8")
    valid = _publish(project, env, "score")
    assert valid.returncode == 0, valid.stderr
    assert json.loads(_remote_file(project, "btc4h_shadow_scores.jsonl")) == score
    assert json.loads(_remote_file(project, "btc4h_shadow_forecasts.jsonl")) == forecast


def test_cannot_rewrite_existing_forecast_or_study_start(tmp_path):
    project, env = _repo(tmp_path)
    research = project / "research"
    anchor_file = research / "btc4h_study_start_utc.txt"
    anchor_file.write_text("2026-11-08T12:00:00Z\n", encoding="utf-8")
    assert _publish(project, env, "anchor").returncode == 0
    ledger = research / "btc4h_shadow_forecasts.jsonl"
    ledger.write_text('{"origin_utc":"A"}\n', encoding="utf-8")
    assert _publish(project, env, "issue").returncode == 0

    ledger.write_text('{"origin_utc":"B"}\n', encoding="utf-8")
    changed = _publish(project, env, "issue")
    assert changed.returncode != 0
    assert "non-append-only" in changed.stderr
    assert json.loads(_remote_file(project, "btc4h_shadow_forecasts.jsonl")) == {"origin_utc": "A"}

    ledger.write_text('{"origin_utc":"A"}\n', encoding="utf-8")
    anchor_file.write_text("2026-11-09T00:00:00Z\n", encoding="utf-8")
    moved = _publish(project, env, "anchor")
    assert moved.returncode != 0
    assert "study anchor changed" in moved.stderr


@pytest.mark.parametrize("phase", ["anchor", "receipt", "score"])
def test_nonissue_phases_cannot_insert_a_forecast(tmp_path, phase):
    project, env = _repo(tmp_path)
    research = project / "research"
    (research / "btc4h_study_start_utc.txt").write_text("2026-11-08T12:00:00Z\n", encoding="utf-8")
    (research / "btc4h_shadow_forecasts.jsonl").write_text(
        '{"origin_utc":"unscheduled"}\n', encoding="utf-8"
    )
    attempted = _publish(project, env, phase)
    assert attempted.returncode != 0
    assert (
        "must not modify forecasts" in attempted.stderr or "outside issue phase" in attempted.stderr
    )



def test_score_phase_cannot_rewrite_a_published_receipt(tmp_path):
    project, env = _repo(tmp_path)
    research = project / "research"
    anchor = "2026-11-08T12:00:00Z"
    (research / "btc4h_study_start_utc.txt").write_text(anchor + "\n", encoding="utf-8")
    assert _publish(project, env, "anchor").returncode == 0
    (research / "btc4h_shadow_forecasts.jsonl").write_text(
        '{"origin_utc":"A"}\n', encoding="utf-8"
    )
    assert _publish(project, env, "issue").returncode == 0
    receipt_file = research / "btc4h_shadow_publication_receipts.jsonl"
    receipt_file.write_text('{"origin_utc":"A"}\n', encoding="utf-8")
    assert _publish(project, env, "receipt").returncode == 0

    receipt_file.write_text('{"origin_utc":"FORGED"}\n', encoding="utf-8")
    attempt = _publish(project, env, "score")
    assert attempt.returncode != 0
    assert "non-append-only" in attempt.stderr
    assert json.loads(_remote_file(project, "btc4h_shadow_publication_receipts.jsonl")) == {
        "origin_utc": "A"
    }
