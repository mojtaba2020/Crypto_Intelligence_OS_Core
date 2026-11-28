"""Point-in-time numeric fundamental features for an isolated BTC V2 research lane.

No provider fetch, scoring, inference, training or live integration. The input
claim of first availability is NOT independently attested: in particular, a
historical value downloaded today cannot be assigned a fabricated 2015 receipt.
Only validated, timestamp-eligible observed values become training features.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import timedelta
from urllib.parse import urlsplit

from scripts.btc_v2_news_evidence import EvidenceError, utc

# Candidates, not claims of licensed accessible data or predictive power.
# Keep categories stable so missing observations remain visible to models.
METRICS = {
    "macro_cpi_surprise": "macro",
    "macro_fed_policy_rate": "macro",
    "macro_payrolls_surprise": "macro",
    "macro_dollar_index": "macro",
    "macro_real_yield": "macro",
    "macro_global_liquidity": "macro",
    "btc_spot_etf_net_flow_usd": "etf",
    "btc_futures_funding_rate": "derivatives",
    "btc_open_interest_usd": "derivatives",
    "btc_options_skew": "derivatives",
    "btc_active_addresses": "onchain",
    "btc_exchange_netflow_btc": "onchain",
    "btc_hashrate": "onchain",
    "btc_miner_outflow_btc": "onchain",
    "btc_supply_issued_btc": "onchain",
    "btc_market_liquidity_usd": "market",
    "btc_halving_elapsed_days": "cycle",
    "btc_news_sentiment": "narrative",
    "btc_developer_activity": "ecosystem",
}
MAX_EVENTS = 5000
MAX_ABS_VALUE = 1e15
REQUIRED = frozenset(
    {
        "metric_id",
        "value",
        "unit",
        "source",
        "source_url",
        "observation_end_utc",
        "published_at_utc",
        "first_seen_at_utc",
        "fetched_at_utc",
        "revision_id",
    }
)
OPTIONAL = frozenset({"revised_at_utc"})


def validate_observation(raw: dict) -> dict:
    """Check one numeric observation's unit and claimed chronology (not truth)."""
    if not isinstance(raw, dict) or not REQUIRED <= raw.keys() or set(raw) - REQUIRED - OPTIONAL:
        raise EvidenceError("fundamental observation schema mismatch")
    metric = raw["metric_id"]
    if not isinstance(metric, str) or metric not in METRICS:
        raise EvidenceError("unregistered fundamental metric")
    if any(
        not isinstance(raw[k], str) or not raw[k].strip() or len(raw[k]) > 512
        for k in ("unit", "source", "source_url", "revision_id")
    ):
        raise EvidenceError("source, revision and units required")
    value = raw["value"]
    if (
        isinstance(value, bool)
        or not isinstance(value, (float, int))
        or not math.isfinite(float(value))
        or abs(float(value)) > MAX_ABS_VALUE
    ):
        raise EvidenceError("nonfinite or excessive fundamental value")
    parsed = urlsplit(raw["source_url"])
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
    ):
        raise EvidenceError("fundamental source must be HTTPS")
    obs = utc(raw["observation_end_utc"])
    pub = utc(raw["published_at_utc"])
    seen = utc(raw["first_seen_at_utc"])
    fetched = utc(raw["fetched_at_utc"])
    if obs > pub or pub > seen or seen > fetched:
        raise EvidenceError("invalid fundamental publication and collection order")
    revised = utc(raw["revised_at_utc"]) if raw.get("revised_at_utc") else None
    if revised is not None and (revised < pub or revised > seen):
        raise EvidenceError("revision chronology invalid")
    return {
        "metric_id": metric,
        "group": METRICS[metric],
        "value": float(value),
        "unit": raw["unit"],
        "source": raw["source"],
        "source_url": raw["source_url"],
        "revision_id": raw["revision_id"],
        "observation_end": obs,
        "published": pub,
        "first_seen": seen,
        "fetched": fetched,
        "revised": revised,
    }


def summarize_fundamentals(
    observations: list[dict], cutoff_utc: str, *, max_age_days: int = 90
) -> dict:
    """A single as-of snapshot; never convert unavailable values into zeros.

    For a given metric and source, the latest *available version* wins.
    Conflicting sources for one metric are rejected instead of silently merged.
    Strict observed-vintage requirements remain external to this contract.
    """
    cutoff = utc(cutoff_utc)
    if (
        isinstance(max_age_days, bool)
        or not isinstance(max_age_days, int)
        or not 1 <= max_age_days <= 365
    ):
        raise EvidenceError("max_age_days must be 1..365")
    if not isinstance(observations, list) or len(observations) > MAX_EVENTS:
        raise EvidenceError("unbounded fundamental observations")
    selected: dict[str, dict] = {}
    source_per_metric: dict[str, str] = {}
    seen_keys: set[tuple[str, str, str, str]] = set()
    excluded_late = 0
    excluded_stale = 0
    for raw in observations:
        item = validate_observation(raw)
        key = (
            item["metric_id"],
            item["source"],
            item["observation_end"].isoformat(),
            item["revision_id"],
        )
        if key in seen_keys:
            raise EvidenceError("duplicate metric observation revision")
        seen_keys.add(key)
        if item["fetched"] > cutoff or item["first_seen"] > cutoff:
            excluded_late += 1
            continue
        if item["observation_end"] < cutoff - timedelta(days=max_age_days):
            excluded_stale += 1
            continue
        metric = item["metric_id"]
        previous_source = source_per_metric.setdefault(metric, item["source"])
        if previous_source != item["source"]:
            raise EvidenceError("conflicting fundamental sources for one metric")
        current = selected.get(metric)
        rank = (
            item["observation_end"],
            item["first_seen"],
            item["revision_id"],
        )
        if current is None or rank > (
            current["observation_end"],
            current["first_seen"],
            current["revision_id"],
        ):
            selected[metric] = item
    values: dict[str, float | None] = {}
    coverage: dict[str, bool] = {}
    provenance: dict[str, dict | None] = {}
    for metric in sorted(METRICS):
        item = selected.get(metric)
        values[metric] = item["value"] if item else None
        coverage[metric] = item is not None
        provenance[metric] = (
            {
                "source": item["source"],
                "source_url": item["source_url"],
                "unit": item["unit"],
                "revision_id": item["revision_id"],
                "published_at_utc": item["published"].isoformat(),
                "first_seen_at_utc": item["first_seen"].isoformat(),
                "fetched_at_utc": item["fetched"].isoformat(),
            }
            if item
            else None
        )
    return {
        "cutoff_utc": cutoff.isoformat().replace("+00:00", "Z"),
        "values": values,
        "has_value": coverage,
        "provenance": provenance,
        "available_metric_count": sum(coverage.values()),
        "registered_metric_count": len(METRICS),
        "excluded_late": excluded_late,
        "excluded_stale": excluded_stale,
        "independently_verified": False,
        "train_eligible": False,
        "research_status": "SCHEMA_ONLY_NO_PROVENANCE_NO_TRAINING",
    }


def merge_research_features(
    price_features: Mapping[str, float],
    news_summary: dict,
    fundamental_summary: dict,
) -> dict:
    """Build a typed, label-free study record, not model inputs for a live job."""
    if not isinstance(price_features, Mapping) or not price_features:
        raise EvidenceError("price features required")
    if news_summary.get("cutoff_utc") != fundamental_summary.get("cutoff_utc"):
        raise EvidenceError("fusion inputs must have identical cutoffs")
    price: dict[str, float] = {}
    for name, value in price_features.items():
        if (
            not isinstance(name, str)
            or not name
            or isinstance(value, bool)
            or not isinstance(value, (float, int))
            or not math.isfinite(float(value))
        ):
            raise EvidenceError("invalid price feature")
        price[name] = float(value)
    if not isinstance(news_summary.get("count"), int) or news_summary["count"] < 0:
        raise EvidenceError("invalid news evidence summary")
    if fundamental_summary.get("research_status") != "SCHEMA_ONLY_NO_PROVENANCE_NO_TRAINING":
        raise EvidenceError("unsupported fundamentals schema version")
    return {
        "cutoff_utc": fundamental_summary["cutoff_utc"],
        "technical": price,
        "news": {
            "count": news_summary["count"],
            "net_labeled_stance": news_summary["net_labeled_stance"],
            "has_news_coverage": news_summary["has_news_coverage"],
        },
        "fundamental": fundamental_summary["values"],
        "fundamental_missing": {
            name: not available for name, available in fundamental_summary["has_value"].items()
        },
        "train_eligible": False,
        "research_status": "OFFLINE_FUSION_FEATURE_CONTRACT_ONLY",
    }
