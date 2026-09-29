#!/usr/bin/env python3
"""Build gap-safe real multi-timeframe BTC datasets without imputing missing candles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from resample_multitimeframe_ohlcv import aggregate, source_data_identity

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
    report: dict[str, object] = {"exchange": exchange, "timeframes": {}}
    for timeframe in TIMEFRAMES:
        all_closed = aggregate(rows, timeframe)
        complete = aggregate(
            rows,
            timeframe,
            require_complete_buckets=True,
            incomplete_policy="drop",
        )
        dropped = len(all_closed) - len(complete)
        if not complete:
            raise ValueError(f"No complete {timeframe} bars for {exchange}")
        path = output_dir / f"{exchange}_{timeframe}.json"
        path.write_text(json.dumps(complete, separators=(",", ":")) + "\n", encoding="utf-8")
        report["timeframes"][timeframe] = {
            "closed_buckets_seen": len(all_closed),
            "complete_buckets": len(complete),
            "dropped_incomplete_buckets": dropped,
            "data_sha256": source_data_identity(complete),
            "first_timestamp": int(complete[0]["timestamp"]),
            "last_timestamp": int(complete[-1]["timestamp"]),
            "gap_policy": "drop_incomplete_target_bucket_no_imputation",
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
        rows = _load(args.input_dir / f"{exchange}_hourly.json")
        exchanges[exchange] = prepare_exchange(rows, exchange, args.output_dir)
    manifest = {
        "status": "REAL_MULTITIMEFRAME_DATASET_V1",
        "policy": "complete_target_buckets_only_no_imputation",
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
