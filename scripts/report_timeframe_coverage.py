#!/usr/bin/env python3
"""Generate an evidence-based BTC timeframe coverage manifest; no inferred model skill."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

REQUESTED_INPUTS = ("1h", "2h", "3h", "4h", "12h", "1d", "2d", "3d", "1w", "2w", "3w", "1mo", "3mo")
HOURLY_HORIZONS = (1, 4, 12, 24)
DAILY_HORIZONS = (1, 3, 7, 14, 21, 30, 90, 180, 365)


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build(root: Path) -> dict:
    hourly_code = root / "scripts/btc_hourly_prospective.py"
    daily_code = root / "scripts/btc_phase5_prospective.py"
    hourly_workflow = root / ".github/workflows/btc_hourly_prospective.yml"
    hourly = read_jsonl(root / "research/hourly_forecasts.jsonl")
    hourly_scores = read_jsonl(root / "research/hourly_scores.jsonl")
    daily = read_jsonl(root / "research/phase5_forecasts.jsonl")
    rows = []
    for candle in REQUESTED_INPUTS:
        if candle == "1h" and hourly_code.is_file():
            for horizon in HOURLY_HORIZONS:
                issued = {(r.get("version"), r.get("origin_hour_utc"), r.get("horizon_hours")) for r in hourly if r.get("horizon_hours") == horizon}
                resolved = {(r.get("version"), r.get("origin_hour_utc"), r.get("horizon_hours")) for r in hourly_scores if r.get("horizon_hours") == horizon and (r.get("version"), r.get("origin_hour_utc"), r.get("horizon_hours")) in issued and r.get("actual_close_usd", 0) > 0 and r.get("model_absolute_error_usd", -1) >= 0 and r.get("persistence_absolute_error_usd", -1) >= 0}
                rows.append(dict(input_candle=candle, forecast_horizon=f"{horizon}h", code_path=str(hourly_code.relative_to(root)), workflow=str(hourly_workflow.relative_to(root)) if hourly_workflow.is_file() else None, ledger="research/hourly_forecasts.jsonl", issued_count=len(issued), resolved_count=len(resolved), status="resolved_and_scored" if resolved else "issuing" if issued else "implemented_unverified", research_only=True))
        elif candle == "1d" and daily_code.is_file():
            for horizon in DAILY_HORIZONS:
                issued = {(r.get("version"), r.get("origin_day"), r.get("horizon_days")) for r in daily if r.get("horizon_days") == horizon}
                rows.append(dict(input_candle=candle, forecast_horizon=f"{horizon}d", code_path=str(daily_code.relative_to(root)), workflow=".github/workflows/btc_phase5_prospective.yml" if (root / ".github/workflows/btc_phase5_prospective.yml").is_file() else None, ledger="research/phase5_forecasts.jsonl", issued_count=len(issued), resolved_count=None, status="issuing" if issued else "implemented_unverified", research_only=True))
        else:
            rows.append(dict(input_candle=candle, forecast_horizon=None, code_path=None, workflow=None, ledger=None, issued_count=None, resolved_count=None, status="not_verified", research_only=True))
    return {"schema_version": 1, "generated_at_utc": datetime.now(timezone.utc).isoformat(), "coverage": rows, "long_range_2_to_8_years": "exploratory_not_verified", "warning": "Code presence and ledger counts do not establish forecast accuracy. Unknown counts are null, not zero. Daily resolved counts are unavailable until the scoring report is persisted; null is not zero."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"coverage_rows": len(report["coverage"]), "output": str(args.output)}))


if __name__ == "__main__":
    main()
