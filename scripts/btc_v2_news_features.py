"""Conservative, point-in-time news feature extraction for BTC V2.

No network calls, sentiment inference, or claims about price direction.
Labels are supplied by an upstream audited classifier and remain untrusted
until their classification timestamps pass the same cutoff checks.
"""
from __future__ import annotations

from datetime import timedelta
from scripts.btc_v2_news_evidence import EvidenceError, utc, validate_batch

ALLOWED_TOPICS = frozenset({"macro", "etf", "regulation", "security", "onchain", "derivatives", "other"})
ALLOWED_STANCES = frozenset({"positive", "negative", "neutral", "unknown"})


def summarize_news(events: list[dict], cutoff_utc: str, lookback_hours: int = 24) -> dict:
    if not isinstance(lookback_hours, int) or isinstance(lookback_hours, bool) or not 1 <= lookback_hours <= 168:
        raise EvidenceError("lookback_hours must be integer 1..168")
    cutoff = utc(cutoff_utc)
    validated = validate_batch(events, cutoff_utc)
    topic_counts = {key: 0 for key in sorted(ALLOWED_TOPICS)}
    stance_counts = {key: 0 for key in sorted(ALLOWED_STANCES)}
    included = 0
    for original, row in zip(events, validated):
        observed = utc(row["first_seen_at_utc"])
        if observed < cutoff - timedelta(hours=lookback_hours):
            continue
        topic = original.get("topic", "other")
        stance = original.get("stance", "unknown")
        if topic not in ALLOWED_TOPICS or stance not in ALLOWED_STANCES:
            raise EvidenceError("unknown topic or stance")
        if stance != "unknown" or topic != "other":
            classified_at = original.get("classified_at_utc")
            if not classified_at:
                raise EvidenceError("labeled evidence requires classified_at_utc")
            classified = utc(classified_at)
            if classified > cutoff or classified < observed:
                raise EvidenceError("classification unavailable at cutoff")
        topic_counts[topic] += 1
        stance_counts[stance] += 1
        included += 1
    return {
        "cutoff_utc": cutoff.isoformat().replace("+00:00", "Z"),
        "lookback_hours": lookback_hours,
        "count": included,
        "topic_counts": topic_counts,
        "stance_counts": stance_counts,
        "net_labeled_stance": stance_counts["positive"] - stance_counts["negative"],
        "has_news_coverage": included > 0,
    }
