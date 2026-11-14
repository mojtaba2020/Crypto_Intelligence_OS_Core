"""Synthetic receipt and actual shell publisher failure cases, using local bare Git."""

import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from scripts.btc4h_delivery_integrity import (
    canonical_line,
    make_receipt,
    validate_receipt,
    verify_stored_receipt,
)

GIT = shutil.which("git") or "/usr/bin/git"
BASH = shutil.which("bash") or "/bin/bash"
PUBLISHER = Path(__file__).resolve().parents[1] / ".github/scripts/publish_btc4h_continuous.sh"


def git(cwd, *args):
    return (
        subprocess.run([GIT, *args], cwd=cwd, check=True, capture_output=True)  # noqa: S603
        .stdout.decode()
        .strip()
    )


@pytest.fixture
def row():
    return dict(
        version="test",
        origin_utc="2026-11-15T08:00:00Z",
        issued_at_utc="2026-11-15T08:12:00Z",
        target_5m_bar_open_utc="2026-11-15T12:10:00Z",
        target_5m_close_utc="2026-11-15T12:15:00Z",
    )


def receipt(row):
    return make_receipt(
        row,
        remote_sha="a" * 40,
        remote_content=canonical_line(row),
        confirmed_at=datetime(2026, 11, 15, 8, 13, tzinfo=UTC),
        run_id="synthetic",
    )


@pytest.mark.parametrize(
    "change",
    [
        {"forecast_canonical_line_sha256": "0" * 64},
        {"remote_issue_commit_sha": "not-a-sha"},
        {"issued_at_utc": "2026-11-15T08:11:00Z"},
        {"first_party_remote_confirmed_at_utc": "2026-11-15T12:15:00Z"},
        {"first_party_remote_confirmed_at_utc": "2026-11-15T12:10:00Z"},
        {"remote_ref_was_fetched_and_compared": False},
        {"independent_time_witness": True},
    ],
)
def test_receipt_tampering_rejected(row, change):
    witness = receipt(row)
    witness.update(change)
    with pytest.raises(ValueError):
        validate_receipt(row, witness)


@pytest.mark.parametrize("content", [b"", b"{}\n"])
def test_publication_missing_from_remote_rejected(row, content):
    with pytest.raises(ValueError, match="exactly one"):
        make_receipt(
            row,
            remote_sha="a" * 40,
            remote_content=content,
            confirmed_at=datetime(2026, 11, 15, 8, 13, tzinfo=UTC),
            run_id="test",
        )


@pytest.fixture
def local_remote(tmp_path):
    remote = tmp_path / "remote.git"
    repo = tmp_path / "repo"
    git(tmp_path, "init", "--bare", str(remote))
    git(tmp_path, "clone", str(remote), str(repo))
    git(repo, "config", "user.email", "test@example.invalid")
    git(repo, "config", "user.name", "Synthetic test")
    (repo / "README").write_text("synthetic\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "synthetic seed")
    (repo / "research").mkdir()
    (repo / "research/btc4h_continuous_start_utc.txt").write_text("2026-11-15T08:00:00Z\n")
    return repo, remote


def publish(repo, phase):
    env = {**os.environ, "GITHUB_WORKSPACE": str(repo), "GITHUB_RUN_ID": "synthetic"}
    return subprocess.run(  # noqa: S603 - local test repositories and fixed tools only.
        [BASH, str(PUBLISHER), phase], cwd=repo, env=env, capture_output=True, text=True
    )


def test_shell_publisher_append_only_and_stale_writer_race(local_remote, row):
    repo, _ = local_remote
    assert publish(repo, "anchor").returncode == 0
    ledger = repo / "research/btc4h_continuous_forecasts.jsonl"
    ledger.write_bytes(canonical_line(row))
    assert publish(repo, "issue").returncode == 0
    # Duplicate invocation is a no-op, not evidence of a new forecast.
    head = git(repo, "ls-remote", "origin", "refs/heads/data/btc4h-continuous-forward")
    assert publish(repo, "issue").returncode == 0
    assert git(repo, "ls-remote", "origin", "refs/heads/data/btc4h-continuous-forward") == head
    # A stale runner proposing different content at the same origin fails closed.
    ledger.write_text(json.dumps({**row, "version": "tampered"}) + "\n")
    failed = publish(repo, "issue")
    assert failed.returncode != 0
    assert "non-append-only" in failed.stderr
    assert git(repo, "ls-remote", "origin", "refs/heads/data/btc4h-continuous-forward") == head


def test_shell_publication_rejection_is_failure(local_remote, row):
    repo, remote = local_remote
    assert publish(repo, "anchor").returncode == 0
    hook = remote / "hooks/pre-receive"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    (repo / "research/btc4h_continuous_forecasts.jsonl").write_bytes(canonical_line(row))
    assert publish(repo, "issue").returncode != 0


def test_receipt_checks_actual_commit_not_only_sha_shape(local_remote, row, monkeypatch):
    repo, _ = local_remote
    monkeypatch.chdir(repo)
    path = "research/btc4h_continuous_forecasts.jsonl"
    Path(path).write_bytes(canonical_line(row))
    git(repo, "add", ".")
    git(repo, "commit", "-m", "synthetic forecast")
    witness = receipt(row)
    witness["remote_issue_commit_sha"] = git(repo, "rev-parse", "HEAD")
    verify_stored_receipt(row, witness, path)
    witness["remote_issue_commit_sha"] = git(repo, "rev-parse", "HEAD^")
    with pytest.raises(subprocess.CalledProcessError):
        verify_stored_receipt(row, witness, path)


def test_remote_publication_must_leave_four_full_hours(row):
    row["version"] = "btc4h-continuous-v2-ridge100"
    with pytest.raises(ValueError, match="less than four hours"):
        make_receipt(
            row,
            remote_sha="a" * 40,
            remote_content=canonical_line(row),
            confirmed_at=datetime(2026, 11, 15, 8, 16, tzinfo=UTC),
            run_id="test",
        )


def scored_fixture():
    from scripts.btc4h_delivery_integrity import canonical_digest

    forecast = dict(
        version="btc4h-continuous-v2-ridge100",
        origin_utc="2026-11-15T08:00:00Z",
        issued_at_utc="2026-11-15T08:12:00Z",
        target_5m_bar_open_utc="2026-11-15T12:10:00Z",
        target_5m_close_utc="2026-11-15T12:15:00Z",
        origin_reference_close_usd=100.0,
        price_forecasts_usd={
            n: 100.0
            for n in ("volume_interaction", "price_plus_volume", "price_only", "persistence")
        },
    )
    score = {
        k: forecast[k]
        for k in (
            "version",
            "origin_utc",
            "issued_at_utc",
            "target_5m_bar_open_utc",
            "target_5m_close_utc",
        )
    }
    score.update(
        actual_close_usd=100.0,
        target_observed_at_utc="2026-11-15T12:16:00Z",
        forecast_canonical_line_sha256=canonical_digest(forecast),
        absolute_log_price_errors={n: 0.0 for n in forecast["price_forecasts_usd"]},
        direction_correct_if_nonflat={n: None for n in forecast["price_forecasts_usd"]},
    )
    return forecast, score


@pytest.mark.parametrize(
    "change",
    [
        {"issued_at_utc": "2026-11-15T08:11:00Z"},
        {"forecast_canonical_line_sha256": "0" * 64},
        {"target_observed_at_utc": "2026-11-15T12:14:00Z"},
        {"actual_close_usd": 101.0},
    ],
)
def test_score_wrong_identity_hash_maturity_or_loss_rejected(change):
    from scripts.btc4h_delivery_integrity import validate_score_match

    forecast, score = scored_fixture()
    validate_score_match(forecast, score)
    score.update(change)
    with pytest.raises(ValueError):
        validate_score_match(forecast, score)


def test_persian_report_missing_score_and_wrong_hash(tmp_path, monkeypatch):
    from scripts import btc4h_delivery_report as report

    forecast, score = scored_fixture()
    prefix = "btc4h_continuous"
    (tmp_path / f"{prefix}_forecasts.jsonl").write_bytes(canonical_line(forecast))
    (tmp_path / f"{prefix}_publication_receipts.jsonl").write_bytes(
        canonical_line(receipt(forecast))
    )
    monkeypatch.setattr(report, "verify_stored_receipt", lambda *a: None)
    start = datetime(2026, 11, 15, 8, tzinfo=UTC)
    now = datetime(2026, 11, 15, 13, tzinfo=UTC)
    pending = "\n".join(report.track(tmp_path, prefix, now, start))
    assert "score_pending" in pending
    assert "243.00" in pending
    (tmp_path / f"{prefix}_scores.jsonl").write_bytes(canonical_line(score))
    resolved = "\n".join(report.track(tmp_path, prefix, now, start))
    assert "Persistence" in resolved
    score["forecast_canonical_line_sha256"] = "0" * 64
    (tmp_path / f"{prefix}_scores.jsonl").write_bytes(canonical_line(score))
    assert "score_pending" in "\n".join(report.track(tmp_path, prefix, now, start))


def test_shell_duplicate_origin_append_rejected(local_remote, row):
    repo, _ = local_remote
    assert publish(repo, "anchor").returncode == 0
    ledger = repo / "research/btc4h_continuous_forecasts.jsonl"
    ledger.write_bytes(canonical_line(row) * 2)
    result = publish(repo, "issue")
    assert result.returncode != 0
    assert "duplicate origin" in result.stderr


def test_job_success_is_not_forecast_delivery():
    from scripts.btc4h_delivery_integrity import require_issue_delivery

    with pytest.raises(ValueError, match="NO_NEW_FORECAST"):
        require_issue_delivery(
            {"research_status": "missed_due_to_late_dispatch", "newly_issued": 0},
            [],
            [],
            "research/test.jsonl",
        )


def test_already_issued_without_receipt_is_failure():
    from scripts.btc4h_delivery_integrity import require_issue_delivery

    with pytest.raises(ValueError, match="ISSUANCE_NOT_RECEIPT_VERIFIED"):
        require_issue_delivery(
            {
                "research_status": "already_issued",
                "newly_issued": 0,
                "origin_utc": "2026-11-15T08:00:00Z",
            },
            [],
            [],
            "test.jsonl",
        )
