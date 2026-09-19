"""Canonical identifier helpers."""

import re
from uuid import NAMESPACE_URL, uuid4, uuid5

_PREFIX_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,31}$")
_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,31}_[0-9a-f]{32}$")


def new_id(prefix: str) -> str:
    """Create a globally unique provider-neutral identifier.

    The exact UUID implementation is deliberately hidden behind this function so that
    a future sortable-ID strategy can be introduced without leaking implementation details
    across the Stable Core.
    """
    if not _PREFIX_PATTERN.fullmatch(prefix):
        raise ValueError(
            "ID prefix must start with a lowercase letter and contain only lowercase "
            "letters, digits, or underscores (2-32 characters)."
        )
    return f"{prefix}_{uuid4().hex}"


def stable_id(prefix: str, key: str) -> str:
    """Create a deterministic canonical ID for an immutable external fact.

    The same non-empty key always maps to the same ID.  This is useful for idempotent
    provider records such as an exchange candle, while ``new_id`` remains the default for
    newly created internal events.
    """
    if not _PREFIX_PATTERN.fullmatch(prefix):
        raise ValueError(
            "ID prefix must start with a lowercase letter and contain only lowercase "
            "letters, digits, or underscores (2-32 characters)."
        )
    if not key.strip():
        raise ValueError("Stable ID key cannot be empty.")
    value = uuid5(NAMESPACE_URL, f"crypto-intelligence-os:{prefix}:{key}").hex
    return f"{prefix}_{value}"


def is_valid_id(value: str) -> bool:
    """Return whether ``value`` matches the canonical Phase 0 identifier format."""
    return bool(_ID_PATTERN.fullmatch(value))
