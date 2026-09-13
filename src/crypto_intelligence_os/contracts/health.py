"""Component health contracts."""

from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator

from crypto_intelligence_os.core.time import ensure_utc, utc_now

from .base import StrictContract


class HealthState(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    QUARANTINED = "QUARANTINED"
    UNAVAILABLE = "UNAVAILABLE"
    RETIRED = "RETIRED"


class HealthReport(StrictContract):
    component_id: str = Field(min_length=2, max_length=128)
    component_version: str = Field(min_length=1, max_length=64)
    state: HealthState
    checked_at: datetime = Field(default_factory=utc_now)
    reason_codes: tuple[str, ...] = ()
    details: dict[str, str | int | float | bool | None] = Field(default_factory=dict)

    @field_validator("checked_at")
    @classmethod
    def normalize_checked_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)
