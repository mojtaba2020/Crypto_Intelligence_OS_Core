#!/usr/bin/env python3
"""Generate or validate machine-readable contract schemas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from crypto_intelligence_os.contracts.base import DictEnvelope, ProducerRef, SecurityContext
from crypto_intelligence_os.contracts.errors import ErrorEnvelope
from crypto_intelligence_os.contracts.health import HealthReport

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas"

REGISTRY = {
    "system_envelope.schema.json": DictEnvelope,
    "producer_ref.schema.json": ProducerRef,
    "security_context.schema.json": SecurityContext,
    "error_envelope.schema.json": ErrorEnvelope,
    "health_report.schema.json": HealthReport,
}


def rendered_schemas() -> dict[str, str]:
    output: dict[str, str] = {}
    for filename, model in REGISTRY.items():
        schema: dict[str, Any] = model.model_json_schema(mode="validation")
        output[filename] = json.dumps(schema, indent=2, sort_keys=True) + "\n"
    return output


def write() -> None:
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    for filename, content in rendered_schemas().items():
        (SCHEMA_DIR / filename).write_text(content, encoding="utf-8")


def check() -> int:
    drift: list[str] = []
    for filename, expected in rendered_schemas().items():
        path = SCHEMA_DIR / filename
        if not path.exists() or path.read_text(encoding="utf-8") != expected:
            drift.append(filename)
    if drift:
        print("Schema drift detected:")
        for filename in drift:
            print(f"  - {filename}")
        print("Run: python scripts/export_schemas.py --write")
        return 1
    print("Schema drift check: PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.write:
        write()
        print(f"Wrote {len(REGISTRY)} schemas to {SCHEMA_DIR}")
        return 0
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
