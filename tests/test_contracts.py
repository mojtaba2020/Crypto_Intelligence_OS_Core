from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from crypto_intelligence_os.contracts.base import ProducerRef, SystemEnvelope
from crypto_intelligence_os.contracts.errors import ErrorCategory, ErrorDetail
from crypto_intelligence_os.core.ids import new_id


def test_system_envelope_normalizes_created_at_to_utc() -> None:
    created = datetime(2026, 9, 13, 8, 0, tzinfo=timezone(timedelta(hours=3, minutes=30)))
    envelope = SystemEnvelope[dict[str, str]](
        message_type="TEST",
        created_at=created,
        trace_id=new_id("trace"),
        producer=ProducerRef(component_id="unit-test", component_version="0.1.0"),
        payload={"status": "ok"},
    )
    assert envelope.created_at == datetime(2026, 9, 13, 4, 30, tzinfo=UTC)


def test_system_envelope_rejects_noncanonical_trace_id() -> None:
    with pytest.raises(ValidationError):
        SystemEnvelope[dict[str, str]](
            message_type="TEST",
            trace_id="not-valid",
            producer=ProducerRef(component_id="unit-test", component_version="0.1.0"),
            payload={"status": "ok"},
        )


def test_contracts_forbid_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ProducerRef(component_id="test", component_version="1", surprise=True)  # type: ignore[call-arg]


def test_error_detail_fingerprint_does_not_mutate_original() -> None:
    error = ErrorDetail(
        code="DATA_STALE",
        category=ErrorCategory.DATA_ERROR,
        message="Market data is stale.",
        component_id="market-data",
    )
    updated = error.with_fingerprint()
    assert error.fingerprint is None
    assert updated.fingerprint is not None
    assert updated.error_id == error.error_id
