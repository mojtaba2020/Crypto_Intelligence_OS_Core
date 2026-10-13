"""Adversarial synthetic tests for the offline Stage-6 local receipt inventory."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from scripts.stage6_forward_vintage_receipt import make_local_receipt
from scripts.stage6_local_receipt_inventory import audit_local_receipt_inventory

DAY = 86_400
START = int(datetime(2026, 10, 9, tzinfo=UTC).timestamp())
SOURCE = "bitstamp:BTCUSD:1d"


def _plan(slots: int = 3) -> dict[str, object]:
    return {
        "source": SOURCE,
        "bar_seconds": DAY,
        "first_open_utc": START,
        "stop_open_exclusive_utc": START + slots * DAY,
    }


def _receipt(slot: int, *, payload: bytes = b"synthetic", delay: int = 30) -> dict:
    cutoff = START + (slot + 1) * DAY
    return make_local_receipt(
        payload,
        source=SOURCE,
        bar_open_utc=START + slot * DAY,
        bar_seconds=DAY,
        clock=lambda: datetime.fromtimestamp(cutoff + delay, tz=UTC),
    )


def test_no_local_receipt_is_explicit_and_not_a_missing_exchange_bar() -> None:
    result = audit_local_receipt_inventory(_plan(), [_receipt(2), _receipt(0)])
    assert result["status"] == "UNATTESTED_LOCAL_RECEIPT_INVENTORY"
    assert result["scientific_authorization"] == "NO_RUN"
    assert result["stage7_freeze_authorized"] is False
    assert result["exchange_first_publication_authenticated"] is False
    assert result["independent_source_provenance_verified"] is False
    assert result["scheduled_slots"] == 3
    assert result["missing_local_receipt_slots"] == 1
    assert [row["status"] for row in result["slots"]] == [
        "ONE_LOCAL_RECEIPT",
        "NO_LOCAL_RECEIPT",
        "ONE_LOCAL_RECEIPT",
    ]


def test_distinct_response_bytes_reported_without_price_revision_claim() -> None:
    result = audit_local_receipt_inventory(
        _plan(1), [_receipt(0, payload=b"initial"), _receipt(0, payload=b"revised", delay=40)]
    )
    assert result["response_byte_change_slots"] == 1
    assert result["slots"][0]["status"] == "RESPONSE_BYTES_DIFFER"
    assert result["slots"][0]["distinct_raw_response_digest_count"] == 2
    assert "price" not in str(result).lower()


def test_same_bytes_at_different_observation_times_are_explicit_repeats() -> None:
    result = audit_local_receipt_inventory(
        _plan(1), [_receipt(0), _receipt(0, delay=45)]
    )
    assert result["repeated_same_response_slots"] == 1
    assert result["response_byte_change_slots"] == 0
    assert result["slots"][0]["status"] == "REPEATED_SAME_RESPONSE_BYTES"


def test_exact_receipt_replay_fails_closed() -> None:
    packet = _receipt(0)
    with pytest.raises(ValueError, match="Repeated identical receipt"):
        audit_local_receipt_inventory(_plan(1), [packet, packet])


def test_out_of_order_input_is_canonicalized_to_fixed_slots() -> None:
    records = [_receipt(2), _receipt(0), _receipt(1)]
    assert audit_local_receipt_inventory(_plan(), records) == audit_local_receipt_inventory(
        _plan(), records[::-1]
    )


def test_missing_all_receipts_is_not_fabricated_as_source_gaps() -> None:
    result = audit_local_receipt_inventory(_plan(), [])
    assert result["missing_local_receipt_slots"] == 3
    assert result["local_receipt_count"] == 0


@pytest.mark.parametrize(
    "modification",
    [
        {"future_return": 0.9},
        {"untrusted_source_revision": "yes"},
        {"source": "bitfinex:BTCUSD:1d"},
        {"bar_seconds": 3_600},
    ],
)
def test_closed_plan_schema_and_identity_reject_unreviewed_fields(
    modification: dict[str, object],
) -> None:
    plan = _plan()
    plan.update(modification)
    with pytest.raises(ValueError):
        audit_local_receipt_inventory(plan, [])


def test_receipt_source_mismatch_fails_without_relabeling() -> None:
    different = make_local_receipt(
        b"synthetic",
        source="bitfinex:BTCUSD:1d",
        bar_open_utc=START,
        bar_seconds=DAY,
        clock=lambda: datetime.fromtimestamp(START + DAY + 30, tz=UTC),
    )
    with pytest.raises(ValueError, match="outside the fixed"):
        audit_local_receipt_inventory(_plan(1), [different])


def test_receipt_outside_schedule_fails_instead_of_adding_a_slot() -> None:
    with pytest.raises(ValueError, match="outside the fixed"):
        audit_local_receipt_inventory(_plan(1), [_receipt(1)])


@pytest.mark.parametrize("receipts", ["raw text", b"raw bytes", [None], [42]])
def test_invalid_receipt_sequences_cannot_make_false_inventory(receipts: object) -> None:
    with pytest.raises(ValueError):
        audit_local_receipt_inventory(_plan(), receipts)


def test_reject_large_plan_or_many_receipts_before_allocation() -> None:
    with pytest.raises(ValueError, match="budget"):
        audit_local_receipt_inventory(_plan(2_049), [])
    with pytest.raises(ValueError, match="oversized"):
        audit_local_receipt_inventory(_plan(1), [_receipt(0)] * 8_193)


def test_noncanonical_and_reversed_schedule_bounds_are_rejected() -> None:
    for stop in (START, START - DAY, START + DAY + 1, True, None):
        plan = _plan(1)
        plan["stop_open_exclusive_utc"] = stop
        with pytest.raises(ValueError):
            audit_local_receipt_inventory(plan, [])


def test_price_payload_is_not_returned_in_summary() -> None:
    raw = b"secret_value=12345"
    summary = audit_local_receipt_inventory(_plan(1), [_receipt(0, payload=raw)])
    assert "12345" not in str(summary)
    assert "raw_response_sha256" not in str(summary)
