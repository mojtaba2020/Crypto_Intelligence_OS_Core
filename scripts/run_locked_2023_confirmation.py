#!/usr/bin/env python3
"""Zero-cost one-command execution of the locked 2023 Bitstamp confirmation."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / "long-history"
DATABASE = ARTIFACTS / "bitstamp-btcusd-1h.sqlite"
INGESTION_REPORT = ARTIFACTS / "bitstamp-btcusd-1h-report.json"
CONFIRMATION = ARTIFACTS / "range-mean-6h-2023-confirmation.json"
PREREG = ROOT / "research" / "prereg_range_mean_6h_down_low_vol_12h_v1.json"


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],  # noqa: S607
            cwd=ROOT,
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "LOCAL_GIT_SHA_UNAVAILABLE"


def _run(command: list[str]) -> None:
    # Command lists are constructed only from fixed repo paths and sys.executable.
    subprocess.run(command, cwd=ROOT, check=True)  # noqa: S603


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--reuse-validated-archive",
        action="store_true",
        help="Skip network backfill only when the existing report/archive validate.",
    )
    args = parser.parse_args()
    ARTIFACTS.mkdir(parents=True, exist_ok=True)

    if not args.reuse_validated_archive:
        # Primary confirmation starts clean so stale observations cannot mix in.
        for stale in (DATABASE, INGESTION_REPORT, CONFIRMATION):
            stale.unlink(missing_ok=True)
        _run(
            [
                sys.executable,
                "scripts/backfill_bitstamp_hourly.py",
                "--start",
                "2023-01-01T00:00:00+00:00",
                "--end",
                "2024-01-01T00:00:00+00:00",
                "--database",
                str(DATABASE),
                "--report",
                str(INGESTION_REPORT),
            ]
        )

    if not DATABASE.exists() or not INGESTION_REPORT.exists():
        raise FileNotFoundError(
            "Validated 2023 archive/report missing; run without --reuse-validated-archive."
        )

    _run(
        [
            sys.executable,
            "scripts/confirm_hourly_regime_hypothesis.py",
            "--database",
            str(DATABASE),
            "--preregistration",
            str(PREREG),
            "--ingestion-report",
            str(INGESTION_REPORT),
            "--runner-git-sha",
            _git_sha(),
            "--output",
            str(CONFIRMATION),
        ]
    )

    result = json.loads(CONFIRMATION.read_text(encoding="utf-8"))
    summary = {
        "decision": result["decision"],
        "regime_samples": result["regime_samples"],
        "validated_bar_count": result["validated_bar_count"],
        "canonical_data_sha256": result["canonical_data_sha256"],
        "preregistration_sha256": result["preregistration_sha256"],
        "runner_git_sha": result["runner_git_sha"],
        "ingestion_chain_of_custody": result["ingestion_chain_of_custody"],
        "confirmation_artifact": str(CONFIRMATION),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
