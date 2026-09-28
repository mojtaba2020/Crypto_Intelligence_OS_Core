#!/usr/bin/env python3
"""Build a fail-closed hourly model registry from statistical evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

HORIZONS = (1, 2, 3, 4, 12)


def build(judge: dict, prospective: dict | None = None) -> dict:
    rows = {int(row["horizon_hours"]): row for row in judge.get("results", [])}
    if set(rows) != set(HORIZONS):
        raise ValueError("Judge must cover locked hourly horizons")
    prospective_rows = {}
    if prospective:
        prospective_rows = {
            (row["version"], int(row["horizon_hours"])): row
            for row in prospective.get("results", [])
        }
    entries = []
    for horizon in HORIZONS:
        row = rows[horizon]
        challenger = row["selected_on_validation"]
        historical_ok = row.get("decision") == "CHALLENGER_ELIGIBLE_FOR_FURTHER_VALIDATION"
        matching = [
            candidate
            for (_version, candidate_horizon), candidate in prospective_rows.items()
            if candidate_horizon == horizon
            and candidate.get("prospective_evidence") == "STATISTICALLY_CONFIRMED_RESEARCH_EDGE"
        ]
        prospective_ok = bool(matching)
        champion = challenger if historical_ok and prospective_ok else "persistence"
        entries.append(
            {
                "horizon_hours": horizon,
                "champion": champion,
                "challenger": challenger,
                "historical_gate_passed": historical_ok,
                "prospective_gate_passed": prospective_ok,
                "live_authorized": historical_ok and prospective_ok,
                "fallback": "persistence",
            }
        )
    return {
        "status": "HOURLY_MODEL_REGISTRY_V1",
        "policy": "fail_closed_historical_plus_prospective_confirmation",
        "automatic_promotion": False,
        "entries": entries,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--judge", type=Path, required=True)
    parser.add_argument("--prospective", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    judge = json.loads(args.judge.read_text())
    prospective = (
        json.loads(args.prospective.read_text())
        if args.prospective and args.prospective.exists()
        else None
    )
    result = build(judge, prospective)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
