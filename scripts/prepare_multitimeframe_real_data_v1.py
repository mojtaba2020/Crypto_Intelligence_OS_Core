#!/usr/bin/env python3
"""Build gap-safe real multi-timeframe BTC datasets without imputing missing candles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from resample_multitimeframe_ohlcv import aggregate, audit_source_rows, source_data_identity

TIMEFRAMES = ("1d", "1w", "1mo")
EXCHANGES = ("bitstamp", "bitfinex")


def _load(path: Path) -> list[dict[str, float]]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError(f"Expected a list of candles in {path}")
    return rows


def prepare_exchange(
    rows: list[dict[str, float]],
    exchange: str,
    output_dir: Path,
) -> dict[str, object]:
    source_audit = audit_source_rows(rows, source_interval_seconds=86400)
    if not source_audit["continuous"]:
        raise ValueError(
            f"Native daily source for {exchange} contains {source_audit['gap_count']} gaps"
        )
    report: dict[str, object] = {
        "exchange": exchange,
        "source_granularity": "native_1d",
        "source_sha256": source_data_identity(rows),
        "source_audit": source_audit,
        "timeframes": {},
    }
    for timeframe in TIMEFRAMES:
        all_closed = aggregate(rows, timeframe, source_interval_seconds=86400)
        complete_count = sum(bool(row["is_complete"]) for row in all_closed)
        incomplete_count = len(all_closed) - complete_count
        if not all_closed:
            raise ValueError(f"No closed {timeframe} bars for {exchange}")
        path = output_dir / f"{exchange}_{timeframe}.json"
        path.write_text(json.dumps(all_closed, separators=(",", ":")) + "\n", encoding="utf-8")
        report["timeframes"][timeframe] = {
            "closed_buckets_seen": len(all_closed),
            "complete_buckets": complete_count,
            "incomplete_buckets": incomplete_count,
            "dropped_incomplete_buckets": 0,
            "data_sha256": source_data_identity(all_closed),
            "first_timestamp": int(all_closed[0]["timestamp"]),
            "last_timestamp": int(all_closed[-1]["timestamp"]),
            "gap_policy": "preserve_calendar_grid_mark_incomplete_no_imputation",
        }
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    exchanges: dict[str, object] = {}
    for exchange in EXCHANGES:
        rows = _load(args.input_dir / f"{exchange}_daily_native.json")
        exchanges[exchange] = prepare_exchange(rows, exchange, args.output_dir)
    manifest = {
        "status": "REAL_MULTITIMEFRAME_DATASET_V1",
        "policy": "native_daily_exchange_bars_then_calendar_aggregate_no_imputation",
        "exchanges": exchanges,
        "automatic_model_promotion": False,
    }
    (args.output_dir / "prepared_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
