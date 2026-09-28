#!/usr/bin/env python3
"""Zero-cost one-shot execution of the locked 2023 Bitstamp confirmation."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import backfill_bitstamp_hourly as backfill
import confirm_hourly_regime_hypothesis as confirm

START = backfill.utc_date("2023-01-01T00:00:00+00:00")
END = backfill.utc_date("2024-01-01T00:00:00+00:00")
EXPECTED_BARS = 8760


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],  # noqa: S607
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "LOCAL_GIT_SHA_UNAVAILABLE"


def run(output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    database = output_dir / "bitstamp-btcusd-1h.sqlite"
    ingestion_report = output_dir / "bitstamp-btcusd-1h-report.json"
    confirmation_output = output_dir / "range-mean-6h-2023-confirmation.json"
    preregistration = (
        Path(__file__).resolve().parents[1]
        / "research"
        / "prereg_range_mean_6h_down_low_vol_12h_v1.json"
    )

    ingestion = backfill.run(
        start=START,
        end=END,
        database=database,
        report_path=ingestion_report,
    )
    if ingestion["stored_count"] != EXPECTED_BARS:
        raise RuntimeError(f"Locked 2023 archive must contain exactly {EXPECTED_BARS} bars")

    result = confirm.run(
        database,
        preregistration,
        confirmation_output,
        ingestion_report,
        _git_sha(),
    )
    if result["validated_bar_count"] != EXPECTED_BARS:
        raise RuntimeError("Confirmation did not validate exactly 8760 bars")
    if result["ingestion_chain_of_custody"] != "PASS":
        raise RuntimeError("Confirmation provenance chain did not pass")
    if result["canonical_data_sha256"] != ingestion["canonical_data_sha256"]:
        raise RuntimeError("Confirmation and ingestion data fingerprints differ")

    return {
        "status": "LOCKED_2023_CONFIRMATION_EXECUTED",
        "python": sys.version.split()[0],
        "git_sha": result["runner_git_sha"],
        "bars": result["validated_bar_count"],
        "data_sha256": result["canonical_data_sha256"],
        "preregistration_sha256": result["preregistration_sha256"],
        "decision": result["decision"],
        "confirmation_artifact": str(confirmation_output),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/free-2023-confirmation"),
    )
    args = parser.parse_args()
    print(json.dumps(run(args.output_dir), indent=2))


if __name__ == "__main__":
    main()
