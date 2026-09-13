"""Base provider-neutral contracts."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from crypto_intelligence_os.core.ids import is_valid_id, new_id
from crypto_intelligence_os.core.time import ensure_utc, utc_now


class StrictContract(BaseModel):
    """Base class for immutable, strict external/internal contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ProducerRef(StrictContract):
    """Identifies the component that produced a message."""

    component_id: str = Field(min_length=2, max_length=128)
    component_version: str = Field(min_length=1, max_length=64)


class SecurityContext(StrictContract):
    """Non-authoritative security metadata carried with a message.

    Receiving services MUST validate authorization against an authoritative policy service;
    these fields never grant privileges by themselves.
    """

    actor_id: str | None = None
    actor_type: str | None = None
    data_classification: str = "INTERNAL"
    approval_id: str | None = None


class SystemEnvelope[PayloadT](StrictContract):
    """Common envelope for important cross-component messages."""

    schema_version: str = "1.0"
    message_id: str = Field(default_factory=lambda: new_id("msg"))
    message_type: str = Field(min_length=1, max_length=128)
    created_at: datetime = Field(default_factory=utc_now)
    trace_id: str
    task_id: str | None = None
    producer: ProducerRef
    security_context: SecurityContext = Field(default_factory=SecurityContext)
    payload: PayloadT

    @field_validator("message_id", "trace_id", "task_id")
    @classmethod
    def validate_canonical_ids(cls, value: str | None) -> str | None:
        if value is not None and not is_valid_id(value):
            raise ValueError("Identifier does not match the canonical Phase 0 ID format.")
        return value

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class DictEnvelope(SystemEnvelope[dict[str, Any]]):
    """Concrete envelope used for schema export and generic structured payloads."""
