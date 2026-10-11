"""Bounded read-only OpenAI reviewers. No model training, OOS or promotion."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from scripts import challenger_v3_real_agent_runtime as runtime

MODEL = "gpt-5.6"
MAX_PROMPT_BYTES = 12_000
MAX_OUTPUT_TOKENS = 2_400
ROLES = {"STATS-02": "statistics", "AUDIT-02": "leakage_audit", "FEATURE-02": "feature_research"}
EVIDENCE_ID = "wave2-context"


def maximum_usd(prompt_bytes: int) -> float:
    if isinstance(prompt_bytes, bool) or not isinstance(prompt_bytes, int) or prompt_bytes < 0:
        raise ValueError("invalid prompt byte count")
    return (4 * prompt_bytes + 20 * MAX_OUTPUT_TOKENS) / 1_000_000


def preflight(task_id: str, root: Path) -> tuple[Path, Path, Path]:
    if task_id not in ROLES:
        raise ValueError("task not in closed reviewer roster")
    if os.environ.get("OPENAI_MODEL") != MODEL:
        raise ValueError("unapproved model or pricing")
    folder = root / "research/v3_agent_wave2"
    task = folder / "tasks" / f"{task_id}.json"
    manifest = folder / "manifest.json"
    info = runtime.load_task(task)
    if info["task_id"] != task_id or info["role"] != ROLES[task_id]:
        raise ValueError("task role mismatch")
    context, _ = runtime.load_context(manifest, folder, [EVIDENCE_ID])
    size = len(runtime.build_prompt(info, context).encode("utf-8"))
    if size > MAX_PROMPT_BYTES or maximum_usd(size) > 0.10:
        raise ValueError("provider request exceeds budget")
    return task, manifest, folder


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", choices=tuple(ROLES), required=True)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    task, manifest, folder = preflight(args.task_id, root)
    if args.preflight_only:
        print("Validated development-only evidence and estimated request cap < $0.10")
        return 0
    runtime.MAX_OUTPUT_TOKENS = MAX_OUTPUT_TOKENS
    return runtime.run(
        task, manifest, folder, [EVIDENCE_ID],
        root / "artifacts/challenger-v3-real-agent-wave2", f"{args.task_id}.json"
    )


if __name__ == "__main__":
    raise SystemExit(main())
