"""Render Cron bridge for the independent BTC4h rolling research track.

Starts disabled. Requires an owner-provided, narrowly scoped GitHub Contents
write token, explicit enablement, and removal of the competing GitHub schedule.
Does not modify the frozen formal study, execute trades, or backfill missed slots.
"""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

GIT = shutil.which("git") or "/usr/bin/git"
REPO_URL = "https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core.git"
PINNED_MODEL_SHA = "9de38d2c30c892d6e7ef3d65a0ee5a6507f77dc9"
ROLLING_DATA_BRANCH = "data/btc4h-continuous-forward"
FORMAL_DATA_BRANCH = "data/btc4h-shadow-forward"
SCRIPT_PATHS = (
    "scripts/btc4h_continuous_forward.py",
    "scripts/btc4h_delivery_integrity.py",
    "scripts/btc4h_delivery_report.py",
    ".github/scripts/publish_btc4h_continuous.sh",
)
RESEARCH_FILES = (
    "btc4h_continuous_forecasts.jsonl",
    "btc4h_continuous_scores.jsonl",
    "btc4h_continuous_publication_receipts.jsonl",
    "btc4h_continuous_start_utc.txt",
)
FORMAL_FILES = (
    "btc4h_shadow_forecasts.jsonl",
    "btc4h_shadow_scores.jsonl",
    "btc4h_shadow_publication_receipts.jsonl",
    "btc4h_30d_protocol_20261109.json",
)


def command(*args: str, cwd: Path | None = None, capture: bool = False) -> str:
    result = subprocess.run(  # noqa: S603 - fixed Git/Python tooling with argument arrays
        args,
        cwd=cwd,
        text=True,
        check=True,
        capture_output=capture,
    )
    return result.stdout.strip() if capture else ""


def phase_for(now: datetime) -> str:
    if now.hour % 4:
        raise ValueError("unexpected Render schedule hour; no work")
    if 8 <= now.minute < 15:
        return "issue"
    if 20 <= now.minute < 55:
        return "score"
    raise ValueError("outside authorized Render cron phase window")


def ensure_no_competing_schedule(source: Path) -> None:
    workflow = (source / ".github/workflows/btc4h_continuous.yml").read_text()
    if re.search(r"(?m)^\s+schedule:\s*$", workflow):
        raise RuntimeError(
            "CUTOVER_GUARD: GitHub rolling schedule is still enabled; "
            "Render publishing is forbidden until that schedule is removed"
        )


def configure_git_auth(token: str) -> None:
    # Ephemeral process environment, not a persisted git remote or credential file.
    encoded = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    os.environ["GIT_CONFIG_COUNT"] = "1"
    os.environ["GIT_CONFIG_KEY_0"] = "http.https://github.com/.extraheader"
    os.environ["GIT_CONFIG_VALUE_0"] = f"AUTHORIZATION: basic {encoded}"
    os.environ["GIT_TERMINAL_PROMPT"] = "0"


def restore_data(work: Path) -> None:
    research = work / "research"
    research.mkdir(exist_ok=True)
    command(
        "git",
        "fetch",
        "-q",
        "origin",
        f"refs/heads/{ROLLING_DATA_BRANCH}:refs/remotes/origin/{ROLLING_DATA_BRANCH}",
        cwd=work,
    )
    for filename in RESEARCH_FILES:
        target = research / filename
        blob = f"origin/{ROLLING_DATA_BRANCH}:research/{filename}"
        existing = subprocess.run(  # noqa: S603 - fixed Git/Python tooling with argument arrays
            [GIT, "cat-file", "-e", blob],
            cwd=work,
            check=False,
            capture_output=True,
        )
        if existing.returncode == 0:
            target.write_bytes(
                subprocess.run(  # noqa: S603 - fixed Git/Python tooling with argument arrays
                    [GIT, "show", blob],
                    cwd=work,
                    check=True,
                    capture_output=True,
                ).stdout
            )
        elif filename == "btc4h_continuous_start_utc.txt":
            raise RuntimeError("rolling study anchor is missing: fail closed")
        else:
            target.touch()


def run_model(work: Path, phase: str, code_sha: str) -> dict:
    result_path = work / ".research" / f"continuous_{phase}.json"
    result_path.parent.mkdir(exist_ok=True)
    command(
        sys.executable,
        "-m",
        "scripts.btc4h_continuous_forward",
        "--phase",
        phase,
        "--ledger",
        "research/btc4h_continuous_forecasts.jsonl",
        "--score-ledger",
        "research/btc4h_continuous_scores.jsonl",
        "--report",
        str(result_path),
        "--code-sha",
        code_sha,
        cwd=work,
    )
    return json.loads(result_path.read_text())


def publish(work: Path, phase: str) -> None:
    command("bash", ".github/scripts/publish_btc4h_continuous.sh", phase, cwd=work)


def receipt_for_new_issue(work: Path, run_id: str) -> None:
    from scripts.btc4h_delivery_integrity import make_receipt

    branch_ref = f"refs/heads/{ROLLING_DATA_BRANCH}"
    sha = command("git", "ls-remote", "origin", branch_ref, cwd=work, capture=True)
    remote_sha = sha.split()[0]
    if not re.fullmatch(r"[0-9a-f]{40}", remote_sha):
        raise RuntimeError("invalid remote publication SHA")
    command(
        "git",
        "fetch",
        "-q",
        "origin",
        f"{branch_ref}:refs/remotes/origin/{ROLLING_DATA_BRANCH}",
        cwd=work,
    )
    remote_content = subprocess.run(  # noqa: S603 - fixed Git/Python tooling with argument arrays
        [GIT, "show", f"{remote_sha}:research/btc4h_continuous_forecasts.jsonl"],
        cwd=work,
        check=True,
        capture_output=True,
    ).stdout
    ledger = work / "research/btc4h_continuous_forecasts.jsonl"
    if remote_content != ledger.read_bytes():
        raise RuntimeError("remote publication bytes differ: fail closed")
    forecast = json.loads(ledger.read_text().splitlines()[-1])
    receipt = make_receipt(
        forecast,
        remote_sha=remote_sha,
        remote_content=remote_content,
        confirmed_at=datetime.now(UTC),
        run_id=run_id,
    )
    receipt_file = work / "research/btc4h_continuous_publication_receipts.jsonl"
    with receipt_file.open("a", encoding="utf-8") as output:
        output.write(json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n")
        output.flush()
        os.fsync(output.fileno())
    publish(work, "receipt")


def verify_issued(work: Path, result: dict) -> None:
    from scripts.btc4h_delivery_integrity import require_issue_delivery

    forecasts = [
        json.loads(line)
        for line in (work / "research/btc4h_continuous_forecasts.jsonl")
        .read_text()
        .splitlines()
        if line.strip()
    ]
    receipts = [
        json.loads(line)
        for line in (work / "research/btc4h_continuous_publication_receipts.jsonl")
        .read_text()
        .splitlines()
        if line.strip()
    ]
    require_issue_delivery(
        result,
        forecasts,
        receipts,
        "research/btc4h_continuous_forecasts.jsonl",
    )


def publish_status(work: Path, run_id: str) -> None:
    command(
        "git",
        "fetch",
        "-q",
        "origin",
        f"refs/heads/{FORMAL_DATA_BRANCH}:refs/remotes/origin/{FORMAL_DATA_BRANCH}",
        cwd=work,
    )
    formal = work / ".research/formal"
    formal.mkdir(parents=True, exist_ok=True)
    for filename in FORMAL_FILES:
        raw = subprocess.run(  # noqa: S603 - fixed Git/Python tooling with argument arrays
            [GIT, "show", f"origin/{FORMAL_DATA_BRANCH}:research/{filename}"],
            cwd=work,
            capture_output=True,
            check=True,
        ).stdout
        (formal / filename).write_bytes(raw)
    command(
        sys.executable,
        "-m",
        "scripts.btc4h_delivery_report",
        "--run-id",
        run_id,
        "--output",
        "research/btc4h_continuous_latest_report.md",
        cwd=work,
    )
    publish(work, "report")


def main() -> int:
    if os.getenv("BTC4H_RENDER_ENABLED") != "true":
        print("BTC4H Render connection staged safely: publishing DISABLED.")
        return 0
    source = Path(__file__).resolve().parents[1]
    ensure_no_competing_schedule(source)
    token = os.getenv("BTC4H_GITHUB_WRITE_TOKEN", "")
    if not token:
        raise RuntimeError(
            "BTC4H_GITHUB_WRITE_TOKEN missing; no publication permitted"
        )
    now = datetime.now(UTC)
    phase = phase_for(now)
    configure_git_auth(token)
    run_id = "render-" + now.strftime("%Y%m%dT%H%M%SZ")
    with tempfile.TemporaryDirectory(prefix="btc4h-render-") as scratch:
        root = Path(scratch)
        clone = root / "repo"
        work = root / "frozen"
        command("git", "clone", "-q", "--no-checkout", REPO_URL, str(clone))
        command("git", "fetch", "-q", "origin", PINNED_MODEL_SHA, cwd=clone)
        command("git", "worktree", "add", "-q", "--detach", str(work), PINNED_MODEL_SHA, cwd=clone)
        for relative in SCRIPT_PATHS:
            target = work / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / relative, target)
        os.environ["GITHUB_WORKSPACE"] = str(work)
        os.environ["GITHUB_RUN_ID"] = run_id
        os.environ["GITHUB_STEP_SUMMARY"] = os.devnull
        os.environ["PYTHONPATH"] = os.pathsep.join(
            (str(work), str(work / "src"), os.environ.get("PYTHONPATH", ""))
        )
        restore_data(work)
        if phase == "issue":
            outcome = run_model(work, "issue", os.getenv("RENDER_GIT_COMMIT", "render-main"))
            if outcome.get("newly_issued") == 1:
                publish(work, "issue")
                receipt_for_new_issue(work, run_id)
            verify_issued(work, outcome)
            print("Render issuance verified:", outcome["research_status"])
        else:
            outcome = run_model(work, "score", os.getenv("RENDER_GIT_COMMIT", "render-main"))
            publish(work, "score")
            print("Render score:", outcome["research_status"], outcome["newly_scored"])
        publish_status(work, run_id)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"BTC4H_RENDER_FAILURE: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
