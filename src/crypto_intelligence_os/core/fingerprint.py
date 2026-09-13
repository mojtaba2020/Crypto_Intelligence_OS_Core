"""Stable fingerprints for error grouping and incident correlation."""

from hashlib import sha256


def error_fingerprint(*parts: str) -> str:
    """Create a stable, non-secret fingerprint from normalized error attributes."""
    normalized = "|".join(part.strip().lower() for part in parts)
    return sha256(normalized.encode("utf-8")).hexdigest()[:24]
