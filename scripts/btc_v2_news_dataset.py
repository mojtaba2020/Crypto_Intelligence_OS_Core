"""Offline, deterministic BTC V2 news feature dataset builder.

Input: JSONL records with cutoff_utc and events array. Does not fetch external
sources or create synthetic news. Fails atomically if any record is invalid.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from scripts.btc_v2_news_evidence import EvidenceError, utc
from scripts.btc_v2_news_features import summarize_news


def build_dataset(records: list[dict]) -> list[dict]:
    if not isinstance(records, list):
        raise EvidenceError("records must be list")
    output = []
    seen_cutoffs = set()
    previous = None
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("events"), list):
            raise EvidenceError("record must contain events array")
        cutoff = utc(record.get("cutoff_utc"))
        if cutoff in seen_cutoffs or (previous is not None and cutoff <= previous):
            raise EvidenceError("cutoffs must be strictly increasing and unique")
        seen_cutoffs.add(cutoff)
        previous = cutoff
        output.append(summarize_news(record["events"], record["cutoff_utc"]))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error("input and output must differ")
    records = []
    with args.input.open("r", encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise EvidenceError(f"invalid JSON on line {number}") from exc
    features = build_dataset(records)
    # All input is validated before the output is opened; no partial writes on bad input.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temp = args.output.with_name(args.output.name + ".tmp")
    try:
        with temp.open("w", encoding="utf-8") as stream:
            for row in features:
                stream.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
        temp.replace(args.output)
    finally:
        temp.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
