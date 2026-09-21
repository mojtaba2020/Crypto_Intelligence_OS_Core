"""Run one bounded, read-only research agent; never trade or mutate repository files."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

from scripts.openai_provider_smoke import API_URL, extract_output_text

MODEL = "gpt-4o-mini"
MAX_OUTPUT_TOKENS = 180
MAX_INPUT_CHARS = 900
TASK = (
    "You are A001, a research-quality auditor. Explain in at most three short "
    "sentences why a Bitcoin price forecast must use out-of-sample time-series "
    "validation, a naive baseline, and a clear statement of uncertainty. "
    "Do not predict prices, recommend trades, or claim access to live data."
)


def run() -> int:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        print("Missing provider secret.", file=sys.stderr)
        return 2
    body = {
        "model": MODEL,
        "input": TASK[:MAX_INPUT_CHARS],
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "store": False,
    }
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
    print("agent=A001 task=research_quality_audit status=completed")
    print(output[:1600])
    usage = payload.get("usage", {})
    if isinstance(usage, dict):
        print(
            "usage_input_tokens="
            f"{usage.get('input_tokens', 'unknown')} "
            "usage_output_tokens="
            f"{usage.get('output_tokens', 'unknown')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
