"""Provider-neutral market-data contracts with point-in-time semantics."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import Field, field_validator, model_validator

from crypto_intelligence_os.contracts.base import StrictContract
from crypto_intelligence_os.core.ids import new_id
from crypto_intelligence_os.core.time import ensure_utc

_MARKET_ID_PATTERN = re.compile(r"^market:[a-z0-9][a-z0-9._:-]{2,127}$")
_VENUE_ID_PATTERN = re.compile(r"^venue:[a-z0-9][a-z0-9._-]{1,63}$")
_ASSET_ID_PATTERN = re.compile(r"^asset:[a-z0-9][a-z0-9._-]{1,63}$")
_SOURCE_ID_PATTERN = re.compile(r"^source:[a-z0-9][a-z0-9._:-]{1,127}$")


class MarketType(StrEnum):
    SPOT = "SPOT"
    PERPETUAL = "PERPETUAL"
    FUTURE = "FUTURE"
    OPTION = "OPTION"
    INDEX = "INDEX"


class Timeframe(StrEnum):
    ONE_MINUTE = "1m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    ONE_HOUR = "1h"
    FOUR_HOURS = "4h"
    ONE_DAY = "1d"
    ONE_WEEK = "1w"


class BarStatus(StrEnum):
    PARTIAL = "PARTIAL"
    FINAL = "FINAL"


class DataQualityState(StrEnum):
    GOOD = "GOOD"
    DEGRADED = "DEGRADED"
    POOR = "POOR"
    UNKNOWN = "UNKNOWN"


class MarketInstrument(StrictContract):
    """Canonical identity of a tradable or observed market."""

    instrument_id: str
    venue_id: str
    base_asset_id: str
    quote_asset_id: str
    market_type: MarketType
    symbol: str = Field(min_length=3, max_length=64)

    @field_validator("instrument_id")
    @classmethod
    def validate_instrument_id(cls, value: str) -> str:
        if not _MARKET_ID_PATTERN.fullmatch(value):
            raise ValueError("instrument_id must use the canonical 'market:<...>' format.")
        return value

    @field_validator("venue_id")
    @classmethod
    def validate_venue_id(cls, value: str) -> str:
        if not _VENUE_ID_PATTERN.fullmatch(value):
            raise ValueError("venue_id must use the canonical 'venue:<slug>' format.")
        return value

    @field_validator("base_asset_id", "quote_asset_id")
    @classmethod
    def validate_asset_id(cls, value: str) -> str:
        if not _ASSET_ID_PATTERN.fullmatch(value):
            raise ValueError("Market assets must use canonical 'asset:<slug>' IDs.")
        return value

    @model_validator(mode="after")
    def validate_distinct_assets(self) -> Self:
        if self.base_asset_id == self.quote_asset_id:
            raise ValueError("base_asset_id and quote_asset_id must be different.")
        return self


class OHLCVBar(StrictContract):
    """One provider-neutral OHLCV bar with explicit knowledge timing.

    ``available_at`` is the earliest time the canonical record was eligible to influence
    the system.  Historical replay must never use a record whose ``available_at`` is after
    the replay cutoff.
    """

    bar_id: str = Field(default_factory=lambda: new_id("bar"))
    instrument_id: str
    timeframe: Timeframe
    status: BarStatus = BarStatus.FINAL
    open_time: datetime
    close_time: datetime
    available_at: datetime
    ingested_at: datetime
    open: Decimal = Field(gt=0)
    high: Decimal = Field(gt=0)
    low: Decimal = Field(gt=0)
    close: Decimal = Field(gt=0)
    volume: Decimal = Field(ge=0)
    source_id: str
    quality: DataQualityState = DataQualityState.GOOD

    @field_validator("instrument_id")
    @classmethod
    def validate_instrument_id(cls, value: str) -> str:
        if not _MARKET_ID_PATTERN.fullmatch(value):
            raise ValueError("instrument_id must use the canonical 'market:<...>' format.")
        return value

    @field_validator("source_id")
    @classmethod
    def validate_source_id(cls, value: str) -> str:
        if not _SOURCE_ID_PATTERN.fullmatch(value):
            raise ValueError("source_id must use the canonical 'source:<...>' format.")
        return value

    @field_validator("open_time", "close_time", "available_at", "ingested_at")
    @classmethod
    def normalize_times(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @model_validator(mode="after")
    def validate_bar_semantics(self) -> Self:
        if self.open_time >= self.close_time:
            raise ValueError("open_time must be earlier than close_time.")
        if self.high < max(self.open, self.low, self.close):
            raise ValueError("high must be greater than or equal to open, low, and close.")
        if self.low > min(self.open, self.high, self.close):
            raise ValueError("low must be less than or equal to open, high, and close.")
        if self.available_at < self.open_time:
            raise ValueError("available_at cannot be earlier than open_time.")
        if self.status is BarStatus.FINAL and self.available_at < self.close_time:
            raise ValueError("A FINAL bar cannot be available before close_time.")
        if self.ingested_at < self.available_at:
            raise ValueError("ingested_at cannot be earlier than available_at.")
        return self


class MarketDataSnapshot(StrictContract):
    """Immutable point-in-time package used by research, backtests, and predictions."""

    snapshot_id: str = Field(default_factory=lambda: new_id("snap"))
    instrument: MarketInstrument
    timeframe: Timeframe
    data_cutoff_time: datetime
    bars: tuple[OHLCVBar, ...]

    @field_validator("data_cutoff_time")
    @classmethod
    def normalize_cutoff(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
        previous_open: datetime | None = None
        seen_bar_ids: set[str] = set()
        for bar in self.bars:
            if bar.instrument_id != self.instrument.instrument_id:
                raise ValueError("All bars must belong to the snapshot instrument.")
            if bar.timeframe is not self.timeframe:
                raise ValueError("All bars must use the snapshot timeframe.")
            if bar.available_at > self.data_cutoff_time:
                raise ValueError("Snapshot contains data unavailable at data_cutoff_time.")
            if bar.bar_id in seen_bar_ids:
                raise ValueError("Snapshot contains a duplicate bar_id.")
            if previous_open is not None and bar.open_time <= previous_open:
                raise ValueError("Snapshot bars must be strictly ordered by open_time.")
            previous_open = bar.open_time
            seen_bar_ids.add(bar.bar_id)
        return self
