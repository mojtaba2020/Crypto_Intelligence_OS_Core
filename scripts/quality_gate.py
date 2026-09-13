#!/usr/bin/env python3
"""Run the Phase 0 quality gate locally or in CI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

COMMANDS = [
    [sys.executable, "-m", "ruff", "check", "."],
    [sys.executable, "-m", "ruff", "format", "--check", "."],
    [sys.executable, "-m", "mypy", "src"],
    [sys.executable, "-m", "pytest"],
    [sys.executable, "scripts/check_architecture.py"],
    [sys.executable, "scripts/export_schemas.py", "--check"],
    [sys.executable, "scripts/build_dependency_graph.py"],
]


def main() -> int:
    for command in COMMANDS:
        print(f"\n>>> {' '.join(command)}", flush=True)
        result = subprocess.run(  # noqa: S603 - commands are a fixed internal allowlist.
            command, cwd=ROOT, check=False
        )
        if result.returncode != 0:
            print("\nQUALITY GATE: FAIL")
            return result.returncode
    print("\nQUALITY GATE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
