"""Opt-in RSS collection of official news; no automatic scheduling or trading.

Uses actual fetch time for first_seen_at_utc, even for historical articles.
Publisher timestamps are untrusted and every record must pass evidence checks.
"""

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.request import Request, urlopen

from scripts.btc_v2_news_evidence import EvidenceError, validate_event
from scripts.btc_v2_source_registry import SOURCES


def collect_feed(xml_bytes: bytes, source: str, observed_at_utc: str) -> list[dict]:
    if source not in SOURCES:
        raise EvidenceError("unapproved source")
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise EvidenceError("invalid RSS XML") from exc
    items = root.findall(".//item")
    results = []
    for item in items:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        if not (title and link and pub):
            continue
        try:
            date = parsedate_to_datetime(pub)
            if date.tzinfo is None:
                continue
            published = date.astimezone(UTC).isoformat().replace("+00:00", "Z")
            event = {
                "source": source,
                "url": link,
                "title": title,
                "published_at_utc": published,
                "first_seen_at_utc": observed_at_utc,
                "fetched_at_utc": observed_at_utc,
            }
            results.append(validate_event(event, observed_at_utc))
        except (ValueError, TypeError, EvidenceError):
            continue
    return results


def append_new_evidence(path: Path, rows: list[dict]) -> int:
    """Append one valid JSON record per line, without rewriting history.

    A corrupt previous ledger or an invalid incoming batch blocks all writes.
    The caller must supply a single writer; inter-process locking is separate.
    """
    if not isinstance(rows, list):
        raise EvidenceError("incoming evidence must be a list")
    known = set()
    if path.exists():
        with path.open(encoding="utf-8") as stream:
            for number, line in enumerate(stream, 1):
                if not line.endswith("\n"):
                    raise EvidenceError(f"unterminated existing ledger line {number}")
                try:
                    existing = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise EvidenceError(f"invalid existing ledger JSON at line {number}") from exc
                if not isinstance(existing, dict):
                    raise EvidenceError("existing ledger row must be object")
                evidence_id = existing.get("evidence_id")
                if (
                    not isinstance(evidence_id, str)
                    or not evidence_id.strip()
                    or evidence_id in known
                ):
                    raise EvidenceError("invalid or duplicate existing evidence ID")
                known.add(evidence_id)

    new_lines = []
    for row in rows:
        if not isinstance(row, dict):
            raise EvidenceError("incoming evidence must be object")
        evidence_id = row.get("evidence_id")
        if not isinstance(evidence_id, str) or not evidence_id.strip():
            raise EvidenceError("invalid incoming evidence ID")
        if evidence_id in known:
            continue
        try:
            encoded = json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise EvidenceError("non-serializable incoming evidence") from exc
        new_lines.append(encoded + "\n")
        known.add(evidence_id)

    if new_lines:
        with path.open("a", encoding="utf-8") as stream:
            stream.writelines(new_lines)
            stream.flush()
    return len(new_lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=sorted(SOURCES), required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    request = Request(
        SOURCES[args.source]["url"],
        headers={"User-Agent": "BTC-V2-research/0.1 (contact: repository issue)"},
    )
    with urlopen(request, timeout=20) as response:
        data = response.read(2_000_001)
    if len(data) > 2_000_000:
        raise EvidenceError("feed too large")
    observed = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    rows = collect_feed(data, args.source, observed)
    appended = append_new_evidence(Path(args.output), rows)
    print(json.dumps({"source": args.source, "accepted": len(rows), "new": appended}))


if __name__ == "__main__":
    main()
