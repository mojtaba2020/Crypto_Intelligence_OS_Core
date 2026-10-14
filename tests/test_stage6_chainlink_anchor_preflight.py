"""Synthetic-only tests: Chainlink oracle claims are never source proofs."""

from __future__ import annotations

import pytest
from scripts.stage6_chainlink_anchor_preflight import (
    BTC_USD_PROXY,
    audit_chainlink_anchor_claim,
)


def _claim() -> dict[str, object]:
    return {
        "chain_id": 1,
        "feed_proxy": BTC_USD_PROXY,
        "aggregator_address": "0x" + "a" * 40,
        "phase_id": 4,
        "aggregator_round_id": 17,
        "proxy_round_id": (4 << 64) | 17,
        "block_number": 18_000_000,
        "block_timestamp_utc": 1_700_000_000,
        "block_hash": "0x" + "b" * 64,
        "transaction_hash": "0x" + "c" * 64,
        "log_index": 2,
        "round_updated_at_utc": 1_699_999_999,
        "claimed_block_first_seen_at_utc": 1_700_000_003,
        "forecast_issued_at_utc": 1_700_000_100,
    }


def test_synthetically_consistent_claim_never_authorizes_run() -> None:
    result = audit_chainlink_anchor_claim(_claim())
    assert result["status"] == "UNVERIFIED_ORACLE_METADATA_ONLY"
    assert result["scientific_authorization"] == "NO_RUN"
    assert result["stage7_freeze_authorized"] is False
    assert result["onchain_inclusion_independently_verified"] is False
    assert result["historical_first_availability_verified"] is False
    assert result["source_trade_identity_verified"] is False


@pytest.mark.parametrize(
    ("key", "value", "error"),
    [
        ("chain_id", 8453, "network"),
        ("chain_id", True, "network"),
        ("feed_proxy", "0x" + "d" * 40, "pinned"),
        ("aggregator_address", BTC_USD_PROXY, "Aggregator"),
        ("aggregator_address", "0x" + "0" * 40, "Aggregator"),
        ("phase_id", 0, "phase"),
        ("aggregator_round_id", 0, "aggregator round"),
        ("proxy_round_id", (5 << 64) | 17, "Proxy round"),
        ("proxy_round_id", 17, "Proxy round"),
        ("log_index", True, "event log"),
        ("block_hash", "0x" + "x" * 64, "block hash"),
        ("transaction_hash", "0x" + "0" * 63, "transaction hash"),
    ],
)
def test_bad_network_round_or_hash_is_rejected(key: str, value: object, error: str) -> None:
    data = _claim()
    data[key] = value
    with pytest.raises(ValueError, match=error):
        audit_chainlink_anchor_claim(data)


def test_after_issue_oracle_block_is_blocked() -> None:
    data = _claim()
    data["block_timestamp_utc"] = data["forecast_issued_at_utc"] + 1
    result = audit_chainlink_anchor_claim(data)
    assert "BLOCK_NOT_BEFORE_FORECAST" in result["gaps"]


def test_late_observation_never_backdates_claimed_availability() -> None:
    data = _claim()
    data["claimed_block_first_seen_at_utc"] = data["forecast_issued_at_utc"] + 1
    result = audit_chainlink_anchor_claim(data)
    assert result["status"] == "BLOCKED"
    assert "FIRST_SEEN_NOT_BEFORE_FORECAST" in result["gaps"]


def test_unknown_observation_is_not_a_pit_pass() -> None:
    data = _claim()
    data["claimed_block_first_seen_at_utc"] = None
    result = audit_chainlink_anchor_claim(data)
    assert result["gaps"] == ["FIRST_SEEN_UNKNOWN"]


def test_same_round_across_upgrades_cannot_relabel_phase() -> None:
    data = _claim()
    data["phase_id"] = 3
    with pytest.raises(ValueError, match="Proxy round"):
        audit_chainlink_anchor_claim(data)


def test_timestamp_after_inclusion_and_impossible_first_seen_are_blocked() -> None:
    data = _claim()
    data["round_updated_at_utc"] = data["block_timestamp_utc"] + 1
    data["claimed_block_first_seen_at_utc"] = data["block_timestamp_utc"] - 1
    result = audit_chainlink_anchor_claim(data)
    assert set(result["gaps"]) == {"ROUND_UPDATED_AFTER_BLOCK", "FIRST_SEEN_BEFORE_BLOCK"}


@pytest.mark.parametrize("addition", [{"answer": 95000}, {"target_return": 0.4}])
def test_no_price_or_future_outcome_can_enter_claim(addition: dict) -> None:
    data = _claim()
    data.update(addition)
    with pytest.raises(ValueError, match="non-outcome"):
        audit_chainlink_anchor_claim(data)

def test_claim_first_observed_at_issuance_in_same_second_is_blocked() -> None:
    claim = _claim()
    claim["claimed_block_first_seen_at_utc"] = claim["forecast_issued_at_utc"]
    result = audit_chainlink_anchor_claim(claim)
    assert result["status"] == "BLOCKED"
    assert "FIRST_SEEN_NOT_BEFORE_FORECAST" in result["gaps"]


def test_wrong_proxy_type_is_not_a_valid_feed() -> None:
    claim = _claim()
    claim["feed_proxy"] = None
    with pytest.raises(ValueError, match="pinned"):
        audit_chainlink_anchor_claim(claim)
