"""Read-only Coinbase public candle adapter.

The adapter intentionally supports market-data reads only.  It has no authentication,
order, transfer, or account capabilities.  The API surface is normalized into Stable Core
contracts so Coinbase can be replaced without changing downstream research logic.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Final
from urllib.parse import urlencode

from crypto_intelligence_os.core.ids import stable_id
from crypto_intelligence_os.core.time import ensure_utc
from crypto_intelligence_os.market_data.contracts import (
    BarStatus,
    DataQualityState,
    MarketDataSnapshot,
    MarketInstrument,
    MarketType,
    OHLCVBar,
    SnapshotKnowledgeMode,
    Timeframe,
)

from .transport import HttpResponseError, HttpsJsonTransport, JsonObject, JsonTransport

COINBASE_API_HOST: Final = "api.coinbase.com"
COINBASE_SOURCE_ID: Final = "source:coinbase.advanced-trade.public"
COINBASE_BTC_USD: Final = MarketInstrument(
    instrument_id="market:coinbase:spot:btc-usd",
    venue_id="venue:coinbase",
    base_asset_id="asset:bitcoin",
    quote_asset_id="asset:usd",
    market_type=MarketType.SPOT,
    symbol="BTC/USD",
)

_TIMEFRAME_SECONDS: Final[dict[Timeframe, int]] = {
    Timeframe.ONE_MINUTE: 60,
    Timeframe.FIVE_MINUTES: 5 * 60,
    Timeframe.FIFTEEN_MINUTES: 15 * 60,
    Timeframe.ONE_HOUR: 60 * 60,
    Timeframe.FOUR_HOURS: 4 * 60 * 60,
    Timeframe.ONE_DAY: 24 * 60 * 60,
}
_TIMEFRAME_GRANULARITY: Final[dict[Timeframe, str]] = {
    Timeframe.ONE_MINUTE: "ONE_MINUTE",
    Timeframe.FIVE_MINUTES: "FIVE_MINUTE",
    Timeframe.FIFTEEN_MINUTES: "FIFTEEN_MINUTE",
    Timeframe.ONE_HOUR: "ONE_HOUR",
    Timeframe.FOUR_HOURS: "FOUR_HOUR",
    Timeframe.ONE_DAY: "ONE_DAY",
}
_MAX_CANDLES_PER_REQUEST: Final = 350
_TRANSIENT_STATUS_CODES: Final = frozenset({429, 500, 502, 503, 504})


class CoinbaseDataError(RuntimeError):
    """Provider response could not be safely normalized."""


class UnsupportedTimeframeError(ValueError):
    """Requested Stable Core timeframe has no safe direct Coinbase mapping."""


class CoinbasePublicCandleSource:
    """Fetch final Coinbase spot candles without credentials or trading permissions."""

    def __init__(
        self,
        *,
        transport: JsonTransport | None = None,
        clock: Callable[[], datetime] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        timeout_seconds: float = 10.0,
        max_retries: int = 3,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        self._transport = transport or HttpsJsonTransport()
        self._clock = clock or (lambda: datetime.now(tz=UTC))
        self._sleeper = sleeper
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries

    def fetch_server_time(self) -> datetime:
        """Return Coinbase server time as UTC using a public read-only endpoint."""
        payload = self._get_json("/api/v3/brokerage/time")
        value = payload.get("epochMillis")
        if value is not None:
            try:
                return datetime.fromtimestamp(int(str(value)) / 1000, tz=UTC)
            except (TypeError, ValueError, OverflowError) as exc:
                raise CoinbaseDataError("Invalid Coinbase epochMillis") from exc

        iso = payload.get("iso")
        if not isinstance(iso, str):
            raise CoinbaseDataError("Coinbase server-time response has no usable timestamp")
        try:
            return ensure_utc(datetime.fromisoformat(iso.replace("Z", "+00:00")))
        except ValueError as exc:
            raise CoinbaseDataError("Invalid Coinbase ISO server time") from exc

    def fetch_final_bars(
        self,
        *,
        instrument: MarketInstrument = COINBASE_BTC_USD,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
        as_of: datetime | None = None,
    ) -> tuple[OHLCVBar, ...]:
        """Fetch final candles in ``[start, end)`` that were market-available by ``as_of``.

        ``as_of`` defaults to Coinbase server time.  Current/incomplete candles and candles
        whose conservative one-second public-cache availability boundary is after ``as_of``
        are excluded.  Historical downloads remain marked by their actual ``ingested_at``;
        callers must use SYSTEM_KNOWN snapshot mode when causal system knowledge is required.
        """
        self._validate_instrument(instrument)
        start_utc = ensure_utc(start)
        end_utc = ensure_utc(end)
        if start_utc >= end_utc:
            raise ValueError("start must be earlier than end")

        granularity = self._granularity(timeframe)
        seconds = self._timeframe_seconds(timeframe)
        cutoff = ensure_utc(as_of) if as_of is not None else self.fetch_server_time()
        effective_end = min(end_utc, cutoff)
        if effective_end <= start_utc:
            return ()

        normalized: dict[datetime, OHLCVBar] = {}
        chunk_start = start_utc
        max_window = timedelta(seconds=seconds * _MAX_CANDLES_PER_REQUEST)
        while chunk_start < effective_end:
            chunk_end = min(chunk_start + max_window, effective_end)
            payload = self._fetch_candle_page(
                product_id="BTC-USD",
                start=chunk_start,
                end=chunk_end,
                granularity=granularity,
            )
            page_ingested_at = ensure_utc(self._clock())
            if page_ingested_at < cutoff:
                page_ingested_at = cutoff
            raw_candles = payload.get("candles")
            if not isinstance(raw_candles, list):
                raise CoinbaseDataError("Coinbase candle response must contain a candles list")
            for raw in raw_candles:
                bar = self._normalize_candle(
                    raw=raw,
                    instrument=instrument,
                    timeframe=timeframe,
                    seconds=seconds,
                    ingested_at=page_ingested_at,
                )
                if not chunk_start <= bar.open_time < chunk_end:
                    continue
                if bar.available_at > cutoff:
                    continue
                normalized[bar.open_time] = bar
            chunk_start = chunk_end

        return tuple(normalized[key] for key in sorted(normalized))

    def fetch_system_known_snapshot(
        self,
        *,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
        instrument: MarketInstrument = COINBASE_BTC_USD,
    ) -> MarketDataSnapshot:
        """Fetch a causally safe snapshot of data actually ingested by this system run."""
        source_cutoff = self.fetch_server_time()
        bars = self.fetch_final_bars(
            instrument=instrument,
            timeframe=timeframe,
            start=start,
            end=end,
            as_of=source_cutoff,
        )
        completed_at = ensure_utc(self._clock())
        for bar in bars:
            if bar.ingested_at > completed_at:
                completed_at = bar.ingested_at
        return MarketDataSnapshot(
            instrument=instrument,
            timeframe=timeframe,
            data_cutoff_time=completed_at,
            knowledge_mode=SnapshotKnowledgeMode.SYSTEM_KNOWN,
            bars=bars,
        )

    def fetch_reconstructed_snapshot(
        self,
        *,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
        historical_cutoff: datetime,
        instrument: MarketInstrument = COINBASE_BTC_USD,
    ) -> MarketDataSnapshot:
        """Build an explicitly labeled historical market view without pretending prior ingestion."""
        cutoff = ensure_utc(historical_cutoff)
        bars = self.fetch_final_bars(
            instrument=instrument,
            timeframe=timeframe,
            start=start,
            end=end,
            as_of=cutoff,
        )
        return MarketDataSnapshot(
            instrument=instrument,
            timeframe=timeframe,
            data_cutoff_time=cutoff,
            knowledge_mode=SnapshotKnowledgeMode.RECONSTRUCTED_MARKET_VIEW,
            bars=bars,
        )

    def _fetch_candle_page(
        self,
        *,
        product_id: str,
        start: datetime,
        end: datetime,
        granularity: str,
    ) -> JsonObject:
        query = urlencode(
            {
                "start": str(int(start.timestamp())),
                "end": str(int(end.timestamp())),
                "granularity": granularity,
                "limit": str(_MAX_CANDLES_PER_REQUEST),
            }
        )
        path = f"/api/v3/brokerage/market/products/{product_id}/candles?{query}"
        return self._get_json(path)

    def _get_json(self, path: str) -> JsonObject:
        attempt = 0
        while True:
            try:
                return self._transport.get_json(
                    host=COINBASE_API_HOST,
                    path=path,
                    timeout_seconds=self._timeout_seconds,
                    headers={
                        "Accept": "application/json",
                        "Cache-Control": "no-cache",
                        "User-Agent": "Crypto-Intelligence-OS/0.3",
                    },
                )
            except HttpResponseError as exc:
                if exc.status_code not in _TRANSIENT_STATUS_CODES or attempt >= self._max_retries:
                    raise
                delay = self._retry_delay_seconds(exc.headers, attempt)
                self._sleeper(delay)
                attempt += 1

    @staticmethod
    def _retry_delay_seconds(headers: Mapping[str, str], attempt: int) -> float:
        retry_after = headers.get("retry-after")
        if retry_after is not None:
            try:
                parsed = float(retry_after)
            except ValueError:
                parsed = -1.0
            if parsed >= 0:
                return min(parsed, 30.0)
        return float(min(0.5 * (2**attempt), 8.0))

    @staticmethod
    def _granularity(timeframe: Timeframe) -> str:
        try:
            return _TIMEFRAME_GRANULARITY[timeframe]
        except KeyError as exc:
            raise UnsupportedTimeframeError(
                f"Coinbase public candles do not directly support {timeframe.value}"
            ) from exc

    @staticmethod
    def _timeframe_seconds(timeframe: Timeframe) -> int:
        try:
            return _TIMEFRAME_SECONDS[timeframe]
        except KeyError as exc:
            raise UnsupportedTimeframeError(
                f"Coinbase public candles do not directly support {timeframe.value}"
            ) from exc

    @staticmethod
    def _validate_instrument(instrument: MarketInstrument) -> None:
        if instrument != COINBASE_BTC_USD:
            raise ValueError("Phase 2 Coinbase adapter currently supports only canonical BTC/USD")

    @staticmethod
    def _normalize_candle(
        *,
        raw: object,
        instrument: MarketInstrument,
        timeframe: Timeframe,
        seconds: int,
        ingested_at: datetime,
    ) -> OHLCVBar:
        if not isinstance(raw, dict):
            raise CoinbaseDataError("Coinbase candle entry must be an object")
        try:
            open_time = datetime.fromtimestamp(int(str(raw["start"])), tz=UTC)
            close_time = open_time + timedelta(seconds=seconds)
            open_price = Decimal(str(raw["open"]))
            high_price = Decimal(str(raw["high"]))
            low_price = Decimal(str(raw["low"]))
            close_price = Decimal(str(raw["close"]))
            volume = Decimal(str(raw["volume"]))
        except (KeyError, TypeError, ValueError, OverflowError, InvalidOperation) as exc:
            raise CoinbaseDataError("Malformed Coinbase candle entry") from exc

        # Coinbase public endpoints may be cached for one second.  A one-second lag is a
        # deliberately conservative market-availability boundary for final candle replay.
        available_at = close_time + timedelta(seconds=1)
        bar_key = (
            f"{COINBASE_SOURCE_ID}|{instrument.instrument_id}|{timeframe.value}|"
            f"{open_time.isoformat()}"
        )
        return OHLCVBar(
            bar_id=stable_id("bar", bar_key),
            instrument_id=instrument.instrument_id,
            timeframe=timeframe,
            status=BarStatus.FINAL,
            open_time=open_time,
            close_time=close_time,
            available_at=available_at,
            ingested_at=max(ingested_at, available_at),
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
            source_id=COINBASE_SOURCE_ID,
            quality=DataQualityState.GOOD,
        )
