#!/usr/bin/env python3
"""Generate a conservative static change-impact report from a Git diff."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from collections import defaultdict, deque
from pathlib import Path

from build_dependency_graph import build_graph

ROOT = Path(__file__).resolve().parents[1]
SRC_PREFIX = "src/crypto_intelligence_os/"
SYSTEM_WIDE_FILES = {
    "pyproject.toml",
    ".github/workflows/ci.yml",
    "scripts/quality_gate.py",
    "scripts/check_architecture.py",
}


def path_to_module(path: str) -> str | None:
    if not path.startswith(SRC_PREFIX) or not path.endswith(".py"):
        return None
    relative = path[len("src/") : -len(".py")]
    parts = relative.split("/")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) if parts else None


def transitive_dependents(graph: dict[str, list[str]], changed: set[str]) -> set[str]:
    reverse: dict[str, set[str]] = defaultdict(set)
    for consumer, dependencies in graph.items():
        for dependency in dependencies:
            reverse[dependency].add(consumer)

    impacted = set(changed)
    queue: deque[str] = deque(changed)
    while queue:
        dependency = queue.popleft()
        for consumer in reverse.get(dependency, set()):
            if consumer not in impacted:
                impacted.add(consumer)
                queue.append(consumer)
    return impacted


def changed_files(base: str, head: str) -> list[str]:
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git executable was not found on PATH")

    # The executable is resolved to an absolute path; shell execution is not used.
    result = subprocess.run(  # noqa: S603
        [str(Path(git).resolve()), "diff", "--name-only", "--end-of-options", base, head],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def impact_level(files: list[str]) -> str:
    if any(path in SYSTEM_WIDE_FILES for path in files):
        return "SYSTEM_WIDE"
    if any("/security/" in path or "/risk/" in path for path in files):
        return "CRITICAL_REVIEW"
    if any("/contracts/" in path or "/core/" in path for path in files):
        return "MULTI_MODULE"
    if any(path.startswith(SRC_PREFIX) for path in files):
        return "MODULE"
    return "LOCAL"


def render_report(files: list[str]) -> str:
    graph = build_graph()
    changed_modules = {module for path in files if (module := path_to_module(path))}
    impacted_modules = transitive_dependents(graph, changed_modules)

    lines = [
        "# Change Impact Report",
        "",
        f"**Impact level:** `{impact_level(files)}`",
        "",
        "## Changed files",
    ]
    if files:
        lines.extend(f"- `{path}`" for path in sorted(files))
    else:
        lines.append("- None detected")

    lines.extend(["", "## Directly changed Python modules"])
    if changed_modules:
        lines.extend(f"- `{module}`" for module in sorted(changed_modules))
    else:
        lines.append("- None")

    downstream = impacted_modules - changed_modules
    lines.extend(["", "## Statically detected downstream modules"])
    if downstream:
        lines.extend(f"- `{module}`" for module in sorted(downstream))
    else:
        lines.append("- None detected")

    lines.extend(
        [
            "",
            "## Safety note",
            "This is a conservative static signal, not proof of complete impact coverage. ",
            "Runtime traces, contract tests, schema checks, and regression tests "
            "remain authoritative gates.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--file", action="append", dest="files")
    args = parser.parse_args()

    if args.files:
        files = args.files
    elif args.base:
        files = changed_files(args.base, args.head)
    else:
        parser.error("Provide --base/--head or one or more --file values.")

    print(render_report(files), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
