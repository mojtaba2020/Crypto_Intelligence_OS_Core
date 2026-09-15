"""Canonical asset identity contracts.

Ticker symbols are display labels, not canonical identifiers.  Stable asset IDs are
provider-neutral and remain unchanged when data vendors or exchanges change.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Self

from pydantic import Field, field_validator, model_validator

from crypto_intelligence_os.contracts.base import StrictContract

_ASSET_ID_PATTERN = re.compile(r"^asset:[a-z0-9][a-z0-9._-]{1,63}$")
_NETWORK_ID_PATTERN = re.compile(r"^network:[a-z0-9][a-z0-9._-]{1,63}$")
_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,19}$")


class AssetClass(StrEnum):
    """High-level asset taxonomy used by the Stable Core."""

    NATIVE_CRYPTO = "NATIVE_CRYPTO"
    # "TOKEN" is an asset taxonomy label, not a credential.
    TOKEN = "TOKEN"  # noqa: S105
    FIAT = "FIAT"
    STABLECOIN = "STABLECOIN"
    INDEX = "INDEX"


class CanonicalAsset(StrictContract):
    """Provider-neutral identity for an asset.

    ``asset_id`` is authoritative inside Crypto Intelligence OS.  ``symbol`` is only a
    human-facing label because the same ticker can refer to different assets.
    """

    asset_id: str
    symbol: str
    name: str = Field(min_length=1, max_length=128)
    asset_class: AssetClass
    network_id: str | None = None
    contract_address: str | None = Field(default=None, min_length=1, max_length=256)
    decimals: int | None = Field(default=None, ge=0, le=255)
    active: bool = True

    @field_validator("asset_id")
    @classmethod
    def validate_asset_id(cls, value: str) -> str:
        if not _ASSET_ID_PATTERN.fullmatch(value):
            raise ValueError("asset_id must match the canonical 'asset:<slug>' format.")
        return value

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, value: str) -> str:
        if not _SYMBOL_PATTERN.fullmatch(value):
            raise ValueError("symbol must be an uppercase market symbol.")
        return value

    @field_validator("network_id")
    @classmethod
    def validate_network_id(cls, value: str | None) -> str | None:
        if value is not None and not _NETWORK_ID_PATTERN.fullmatch(value):
            raise ValueError("network_id must match the canonical 'network:<slug>' format.")
        return value

    @model_validator(mode="after")
    def validate_asset_semantics(self) -> Self:
        if self.asset_class is AssetClass.NATIVE_CRYPTO and self.network_id is None:
            raise ValueError("Native crypto assets require a canonical network_id.")
        if self.asset_class is AssetClass.FIAT and self.network_id is not None:
            raise ValueError("Fiat assets cannot have a blockchain network_id.")
        if self.asset_class is AssetClass.FIAT and self.contract_address is not None:
            raise ValueError("Fiat assets cannot have a contract_address.")
        return self
