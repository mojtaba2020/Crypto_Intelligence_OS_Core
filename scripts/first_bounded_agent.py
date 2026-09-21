"""Run one manual, bounded, read-only audit of a supplied forecast report."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from scripts.openai_provider_smoke import API_URL, extract_output_text

MODEL = "gpt-4o-mini"
MAX_OUTPUT_TOKENS = 350
MAX_REPORT_BYTES = 12_000
REQUIRED_FIELDS = (
    "source", "instrument", "first_day", "last_completed_day",
    "horizon_days", "train_examples", "test_examples",
    "model_mae_usd", "persistence_mae_usd",
)


def load_evidence(path: Path) -> dict:
    """Fail closed: no provider call unless a small, valid local report exists."""
    if not path.is_file() or path.stat().st_size > MAX_REPORT_BYTES:
        raise ValueError("Evidence report missing or exceeds size limit")
    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, dict) or any(field not in report for field in REQUIRED_FIELDS):
        raise ValueError("Evidence report lacks required evaluation fields")
    if report["horizon_days"] <= 0 or report["train_examples"] <= 0 or report["test_examples"] <= 0:
        raise ValueError("Evidence report has invalid horizon or sample counts")
    for field in ("model_mae_usd", "persistence_mae_usd"):
        value = report[field]
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value < 1e15:
            raise ValueError("Evidence report has invalid MAE")
    return {field: report[field] for field in REQUIRED_FIELDS}


def run(report_path: Path) -> int:
    try:
        evidence = load_evidence(report_path)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"Evidence rejected: {type(exc).__name__}", file=sys.stderr)
        return 2
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        print("Missing provider secret.", file=sys.stderr)
        return 2
    task = (
        "You are A001, a read-only Bitcoin forecast quality auditor. "
        "Use ONLY the supplied evaluation evidence; never invent data, prices, "
        "tests, split methods, or source access. In at most 180 words: identify "
        "the evidence and compare model MAE with persistence MAE, noting that "
        "lower is better. Mark leakage controls, chronological splits, dataset "
        "completeness and uncertainty calibration NOT ASSESSED unless explicitly "
        "documented. State one concrete next offline verification experiment. "
        "No trading advice or claim of profitability. Evidence JSON: "
        + json.dumps(evidence, sort_keys=True)
    )
    body = {"model": MODEL, "input": task, "max_output_tokens": MAX_OUTPUT_TOKENS, "store": False}
    request = urllib.request.Request(  # noqa: S310
        API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print(f"Agent provider HTTP {exc.code}; response body suppressed.", file=sys.stderr)
        return 1
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"Agent provider connection failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    output = extract_output_text(payload)
    if not output:
        print("Agent returned no text.", file=sys.stderr)
        return 1
    print("agent=A001 task=evidence_grounded_audit status=completed")
    print(output[:2400])
    usage = payload.get("usage", {})
    if isinstance(usage, dict):
        print(f"usage_input_tokens={usage.get('input_tokens', 'unknown')} usage_output_tokens={usage.get('output_tokens', 'unknown')}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    raise SystemExit(run(parser.parse_args().report))
