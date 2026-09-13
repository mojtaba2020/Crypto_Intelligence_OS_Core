#!/usr/bin/env python3
"""Guard Stable Core modules from provider/framework coupling."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STABLE_DIRS = [
    ROOT / "src" / "crypto_intelligence_os" / "core",
    ROOT / "src" / "crypto_intelligence_os" / "contracts",
]

# These belong behind adapters/runtime boundaries, not in the Stable Core.
BANNED_ROOT_IMPORTS = {
    "anthropic",
    "google",
    "langchain",
    "langgraph",
    "mcp",
    "openai",
}


def imported_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def main() -> int:
    violations: list[str] = []
    for directory in STABLE_DIRS:
        for path in sorted(directory.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            bad = sorted(imported_roots(tree) & BANNED_ROOT_IMPORTS)
            if bad:
                relative = path.relative_to(ROOT)
                violations.append(f"{relative}: {', '.join(bad)}")

    if violations:
        print("Architecture drift detected in Stable Core:")
        for violation in violations:
            print(f"  - {violation}")
        return 1

    print("Architecture drift check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
