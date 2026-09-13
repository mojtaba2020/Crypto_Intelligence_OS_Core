"""Structured system error contracts."""

from enum import StrEnum
from typing import Any

from pydantic import Field

from crypto_intelligence_os.core.fingerprint import error_fingerprint
from crypto_intelligence_os.core.ids import new_id

from .base import StrictContract


class ErrorCategory(StrEnum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    DATA_ERROR = "DATA_ERROR"
    MODEL_ERROR = "MODEL_ERROR"
    AGENT_ERROR = "AGENT_ERROR"
    TOOL_ERROR = "TOOL_ERROR"
    ROUTING_ERROR = "ROUTING_ERROR"
    MEMORY_ERROR = "MEMORY_ERROR"
    RESEARCH_ERROR = "RESEARCH_ERROR"
    RISK_ERROR = "RISK_ERROR"
    SECURITY_ERROR = "SECURITY_ERROR"
    TIMEOUT = "TIMEOUT"
    RATE_LIMIT = "RATE_LIMIT"
    CONFLICT = "CONFLICT"
    DEPENDENCY_ERROR = "DEPENDENCY_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class ErrorSeverity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ErrorDetail(StrictContract):
    error_id: str = Field(default_factory=lambda: new_id("err"))
    code: str = Field(min_length=1, max_length=128)
    category: ErrorCategory
    message: str = Field(min_length=1, max_length=2000)
    retryable: bool = False
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    component_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    fingerprint: str | None = None

    def with_fingerprint(self) -> "ErrorDetail":
        """Return a copy containing a stable diagnostic fingerprint."""
        fingerprint = error_fingerprint(
            self.category.value,
            self.code,
            self.component_id or "unknown-component",
        )
        return self.model_copy(update={"fingerprint": fingerprint})


class ErrorEnvelope(StrictContract):
    trace_id: str
    error: ErrorDetail
