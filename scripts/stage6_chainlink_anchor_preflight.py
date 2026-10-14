"""Label-blind sanity check for a *claimed* Ethereum Chainlink oracle anchor.

Offline only: no RPC, prices, events, market data, secrets, or authority to run.
A block hash written in a JSON object is NOT a verified inclusion proof.
"""

from __future__ import annotations

from collections.abc import Mapping

CHAIN_ID = 1
BTC_USD_PROXY = "0xf4030086522a5beea4988f8ca5b36dbc97bee88c"
FIELDS = frozenset(
    {
        "chain_id",
        "feed_proxy",
        "aggregator_address",
        "phase_id",
        "aggregator_round_id",
        "proxy_round_id",
        "block_number",
        "block_timestamp_utc",
        "block_hash",
        "transaction_hash",
        "log_index",
        "round_updated_at_utc",
        "claimed_block_first_seen_at_utc",
        "forecast_issued_at_utc",
    }
)


def _positive_int(value: object, name: str) -> int:
    if type(value) is not int or value <= 0 or value >= 2**80:
        raise ValueError(f"Invalid {name}")
    return value


def _hex(value: object, size: int, name: str) -> str:
    if (
        type(value) is not str
        or not value.startswith("0x")
        or len(value) != 2 + size * 2
        or any(ch not in "0123456789abcdef" for ch in value[2:])
    ):
        raise ValueError(f"Invalid {name}")
    return value


def audit_chainlink_anchor_claim(claim: Mapping[str, object]) -> dict[str, object]:
    """Reject obvious phase/clock contradictions; NEVER approve historic evidence."""
    if not isinstance(claim, Mapping) or set(claim) != FIELDS:
        raise ValueError("Exact non-outcome Chainlink claim schema required")
    if type(claim["chain_id"]) is not int or claim["chain_id"] != CHAIN_ID:
        raise ValueError("Wrong Ethereum network")
    if claim["feed_proxy"] != BTC_USD_PROXY:
        raise ValueError("Wrong pinned BTC/USD standard feed proxy")
    aggregator = _hex(claim["aggregator_address"], 20, "aggregator address")
    if aggregator == BTC_USD_PROXY or aggregator == "0x" + "0" * 40:
        raise ValueError("Aggregator must not be proxy or null")
    phase = _positive_int(claim["phase_id"], "phase")
    round_id = _positive_int(claim["aggregator_round_id"], "aggregator round")
    proxy_round = _positive_int(claim["proxy_round_id"], "proxy round")
    if phase >= 2**16 or round_id >= 2**64 or proxy_round != (phase << 64) | round_id:
        raise ValueError("Proxy round does not match phase and aggregator round")
    _positive_int(claim["block_number"], "block number")
    _hex(claim["block_hash"], 32, "block hash")
    _hex(claim["transaction_hash"], 32, "transaction hash")
    if type(claim["log_index"]) is not int or not 0 <= claim["log_index"] < 2**32:
        raise ValueError("Invalid event log index")

    block_ts = _positive_int(claim["block_timestamp_utc"], "block timestamp")
    updated = _positive_int(claim["round_updated_at_utc"], "round update")
    issued = _positive_int(claim["forecast_issued_at_utc"], "forecast issuance")
    seen = claim["claimed_block_first_seen_at_utc"]
    gaps: list[str] = []
    if updated > block_ts:
        gaps.append("ROUND_UPDATED_AFTER_BLOCK")
    if block_ts >= issued:
        gaps.append("BLOCK_NOT_BEFORE_FORECAST")
    if seen is None:
        gaps.append("FIRST_SEEN_UNKNOWN")
    else:
        seen_ts = _positive_int(seen, "block first seen")
        if seen_ts < block_ts:
            gaps.append("FIRST_SEEN_BEFORE_BLOCK")
        if seen_ts > issued:
            gaps.append("FIRST_SEEN_AFTER_FORECAST")
    return {
        "status": "BLOCKED" if gaps else "UNVERIFIED_ORACLE_METADATA_ONLY",
        "gaps": gaps,
        "scientific_authorization": "NO_RUN",
        "stage7_freeze_authorized": False,
        "onchain_inclusion_independently_verified": False,
        "historical_first_availability_verified": False,
        "source_trade_identity_verified": False,
    }
