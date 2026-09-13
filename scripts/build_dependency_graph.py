#!/usr/bin/env python3
"""Build a static internal Python-module dependency graph."""

from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
PACKAGE = "crypto_intelligence_os"
PACKAGE_ROOT = SRC_ROOT / PACKAGE


def module_name(path: Path) -> str:
    relative = path.relative_to(SRC_ROOT).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def internal_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    current = module_name(path)
    current_parts = current.split(".") if current else [PACKAGE]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == PACKAGE or alias.name.startswith(PACKAGE + "."):
                    found.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                if node.module == PACKAGE or node.module.startswith(PACKAGE + "."):
                    found.add(node.module)
            elif node.level > 0:
                # Resolve relative import to a package-level module approximately.
                base_parts = current_parts[:-1]
                up = node.level - 1
                if up:
                    base_parts = base_parts[:-up]
                if node.module:
                    base_parts += node.module.split(".")
                resolved = ".".join(base_parts)
                if resolved.startswith(PACKAGE):
                    found.add(resolved)
    return found


def build_graph() -> dict[str, list[str]]:
    graph: dict[str, list[str]] = {}
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        module = module_name(path)
        if module:
            graph[module] = sorted(internal_imports(path) - {module})
    return graph


def main() -> int:
    graph = build_graph()
    print(json.dumps(graph, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
