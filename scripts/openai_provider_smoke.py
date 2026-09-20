"""Minimal OpenAI Responses API smoke client for the agent fleet.

Reads OPENAI_API_KEY from the environment. Never stores or prints the key.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API_URL = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = "gpt-5.6-luna"


def extract_output_text(payload: dict) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    parts: list[str] = []
    for item in payload.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts).strip()


def main() -> int:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("OPENAI_API_KEY is not configured.", file=sys.stderr)
        return 2

    model = os.environ.get("OPENAI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    body = {
        "model": model,
        "input": (
            "You are agent A001 in Crypto Intelligence OS. Reply with exactly: PROVIDER_CONNECTED"
        ),
        "max_output_tokens": 32,
        "store": False,
    }
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        print(f"OpenAI API HTTP {exc.code}: {detail[:800]}", file=sys.stderr)
        return 1
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"OpenAI API connection failed: {exc}", file=sys.stderr)
        return 1

    output = extract_output_text(payload)
    print(f"provider=openai model={model}")
    print(f"response={output}")
    return 0 if "PROVIDER_CONNECTED" in output else 1


if __name__ == "__main__":
    raise SystemExit(main())
