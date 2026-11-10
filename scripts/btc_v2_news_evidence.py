"""Fail-closed, point-in-time BTC news evidence validator (stdlib only).

This module does not fetch news, score sentiment, or make price forecasts.
It accepts externally collected metadata as untrusted data and rejects
observations that could not have been known at the forecast cutoff.
"""
from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlsplit
import hashlib
import json


class EvidenceError(ValueError):
    pass


def utc(value: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise EvidenceError("missing timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EvidenceError("invalid timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise EvidenceError("timestamp must have timezone")
    return parsed.astimezone(timezone.utc)


def validate_event(event: dict, cutoff_utc: str) -> dict:
    """Return normalized evidence only if every known-time guard passes."""
    if not isinstance(event, dict):
        raise EvidenceError("event must be object")
    cutoff = utc(cutoff_utc)
    required = ("source", "url", "title", "published_at_utc",
                "first_seen_at_utc", "fetched_at_utc")
    for field in required:
        if not isinstance(event.get(field), str) or not event[field].strip():
            raise EvidenceError("missing " + field)
    url = event["url"].strip()
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise EvidenceError("source URL must be a public HTTPS URL")
    times = {field: utc(event[field]) for field in required[-3:]}
    if times["published_at_utc"] > times["first_seen_at_utc"]:
        raise EvidenceError("first seen before publication")
    if times["first_seen_at_utc"] > times["fetched_at_utc"]:
        raise EvidenceError("fetch before first observation")
    if any(value > cutoff for value in times.values()):
        raise EvidenceError("future or late evidence")
    if event.get("revised_at_utc"):
        revised = utc(event["revised_at_utc"])
        if revised > cutoff:
            raise EvidenceError("revised after forecast cutoff")
    canonical = {field: event[field].strip() for field in ("source", "url", "title")}
    canonical.update({key: value.isoformat().replace("+00:00", "Z") for key, value in times.items()})
    canonical["cutoff_utc"] = cutoff.isoformat().replace("+00:00", "Z")
    canonical["evidence_id"] = hashlib.sha256(
        json.dumps({key: canonical[key] for key in ("source", "url", "published_at_utc")},
                   sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return canonical


def validate_batch(events: list[dict], cutoff_utc: str) -> list[dict]:
    seen = set()
    accepted = []
    for event in events:
        row = validate_event(event, cutoff_utc)
        if row["evidence_id"] in seen:
            raise EvidenceError("duplicate evidence")
        seen.add(row["evidence_id"])
        accepted.append(row)
    return accepted
