"""Offline, label-blind inventory of *local* forward source-response receipts.

No data reads, APIs, scheduling, training, source attestation or authority to
consume reserved/locked data. Missing receipt != missing exchange candle.
Different response bytes != proven OHLCV price revision.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from scripts.stage6_forward_vintage_receipt import _validate_metadata, validate_local_receipt

PLAN_FIELDS = frozenset({"source", "bar_seconds", "first_open_utc", "stop_open_exclusive_utc"})
MAX_SCHEDULED_SLOTS = 2_048
MAX_LOCAL_RECEIPTS = 8_192


def audit_local_receipt_inventory(
    plan: Mapping[str, object], receipts: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    """Inventory a complete *operator-asserted* schedule without using prices or labels."""
    if not isinstance(plan, Mapping) or set(plan) != PLAN_FIELDS:
        raise ValueError("Closed-schema local receipt audit plan required")
    source = plan["source"]
    seconds = plan["bar_seconds"]
    first = plan["first_open_utc"]
    stop = plan["stop_open_exclusive_utc"]
    _validate_metadata(source, first, seconds)
    if type(stop) is not int or stop <= first or stop % seconds:
        raise ValueError("Invalid exclusive UTC stop")
    if (stop - first) % seconds:
        raise ValueError("Incomplete scheduled bar interval")
    n_slots = (stop - first) // seconds
    if n_slots > MAX_SCHEDULED_SLOTS:
        raise ValueError("Schedule exceeds bounded offline inventory budget")
    if (
        not isinstance(receipts, Sequence)
        or isinstance(receipts, (str, bytes))
        or len(receipts) > MAX_LOCAL_RECEIPTS
    ):
        raise ValueError("Invalid or oversized receipt sequence")

    by_open: dict[int, list[Mapping[str, object]]] = {}
    receipt_ids: set[str] = set()
    for receipt in receipts:
        validate_local_receipt(receipt)
        opening = receipt["bar_open_utc"]
        if (
            receipt["source"] != source
            or receipt["bar_seconds"] != seconds
            or not first <= opening < stop
        ):
            raise ValueError("Receipt is outside the fixed source, cadence or schedule")
        rid = receipt["receipt_sha256"]
        if rid in receipt_ids:
            raise ValueError("Repeated identical receipt record is not another observation")
        receipt_ids.add(rid)
        by_open.setdefault(opening, []).append(receipt)

    slots: list[dict[str, object]] = []
    missing = 0
    changed = 0
    repeats = 0
    for opening in range(first, stop, seconds):
        observations = by_open.get(opening, [])
        hashes = {row["raw_response_sha256"] for row in observations}
        if not observations:
            status = "NO_LOCAL_RECEIPT"
            missing += 1
        elif len(hashes) > 1:
            status = "RESPONSE_BYTES_DIFFER"
            changed += 1
        elif len(observations) > 1:
            status = "REPEATED_SAME_RESPONSE_BYTES"
            repeats += 1
        else:
            status = "ONE_LOCAL_RECEIPT"
        slots.append(
            {
                "bar_open_utc": opening,
                "status": status,
                "local_observation_count": len(observations),
                "distinct_raw_response_digest_count": len(hashes),
            }
        )
    return {
        "status": "UNATTESTED_LOCAL_RECEIPT_INVENTORY",
        "scientific_authorization": "NO_RUN",
        "stage7_freeze_authorized": False,
        "exchange_first_publication_authenticated": False,
        "independent_source_provenance_verified": False,
        "scheduled_slots": n_slots,
        "local_receipt_count": len(receipts),
        "missing_local_receipt_slots": missing,
        "response_byte_change_slots": changed,
        "repeated_same_response_slots": repeats,
        "slots": slots,
    }
