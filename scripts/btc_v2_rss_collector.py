"""Opt-in RSS collection of official news; no automatic scheduling or trading.

Uses actual fetch time for first_seen_at_utc, even for historical articles.
Publisher timestamps are untrusted and every record must pass evidence checks.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

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
            published = date.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            event = {
                "source": source, "url": link, "title": title,
                "published_at_utc": published,
                "first_seen_at_utc": observed_at_utc,
                "fetched_at_utc": observed_at_utc,
            }
            results.append(validate_event(event, observed_at_utc))
        except (ValueError, TypeError, EvidenceError):
            continue
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=sorted(SOURCES), required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    request = Request(SOURCES[args.source]["url"], headers={"User-Agent": "BTC-V2-research/0.1 (contact: repository issue)"})
    with urlopen(request, timeout=20) as response:
        data = response.read(2_000_001)
    if len(data) > 2_000_000:
        raise EvidenceError("feed too large")
    observed = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    rows = collect_feed(data, args.source, observed)
    # Append-only; no overwriting an existing evidence ledger.
    with open(args.output, "a", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
