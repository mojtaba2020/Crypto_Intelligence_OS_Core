"""Small HTTPS/JSON transport boundary for market-data providers.

The Stable Core depends on this narrow protocol rather than a vendor SDK.  The default
implementation uses Python's standard library, keeps all requests HTTPS-only, and never
accepts credentials.
"""

from __future__ import annotations

import http.client
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, cast

JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class HttpResponseError(RuntimeError):
    """Non-success response from a read-only provider endpoint."""

    status_code: int
    reason: str
    headers: Mapping[str, str]
    body_preview: str

    def __str__(self) -> str:
        return f"HTTP {self.status_code} {self.reason}: {self.body_preview}"


class JsonTransport(Protocol):
    """Read-only HTTPS JSON transport used by provider adapters."""

    def get_json(
        self,
        *,
        host: str,
        path: str,
        timeout_seconds: float,
        headers: Mapping[str, str] | None = None,
    ) -> JsonObject: ...


class HttpsJsonTransport:
    """Minimal HTTPS GET transport with explicit timeouts and response validation."""

    def get_json(
        self,
        *,
        host: str,
        path: str,
        timeout_seconds: float,
        headers: Mapping[str, str] | None = None,
    ) -> JsonObject:
        if not host or "/" in host or "://" in host:
            raise ValueError("host must be a bare HTTPS hostname")
        if not path.startswith("/"):
            raise ValueError("path must start with '/'")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

        connection = http.client.HTTPSConnection(host, timeout=timeout_seconds)
        try:
            connection.request("GET", path, headers=dict(headers or {}))
            response = connection.getresponse()
            payload = response.read()
            response_headers = {key.lower(): value for key, value in response.getheaders()}
            if not 200 <= response.status < 300:
                preview = payload[:512].decode("utf-8", errors="replace")
                raise HttpResponseError(
                    status_code=response.status,
                    reason=response.reason,
                    headers=response_headers,
                    body_preview=preview,
                )
            try:
                decoded = json.loads(payload)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("Provider returned invalid JSON") from exc
            if not isinstance(decoded, dict):
                raise ValueError("Provider JSON root must be an object")
            return cast(JsonObject, decoded)
        finally:
            connection.close()
