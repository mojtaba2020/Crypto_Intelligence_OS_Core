"""Bitfinex public hourly BTC/USD adapter normalized to provider-neutral OHLCV."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from crypto_intelligence_os.market_data import BarStatus, OHLCVBar, Timeframe

API = "https://api-pub.bitfinex.com/v2/candles/trade:1h:tBTCUSD/hist"
DAILY_API = "https://api-pub.bitfinex.com/v2/candles/trade:1D:tBTCUSD/hist"
SOURCE_ID = "source:bitfinex.public"
INSTRUMENT_ID = "market:bitfinex:spot:btc-usd"
HEADERS = {"User-Agent": "Crypto-Intelligence-OS/1.0", "Accept": "application/json"}
type BitfinexScalar = int | float | str
type BitfinexCandle = list[BitfinexScalar]


def _parse(
    payload: list[BitfinexCandle],
    *,
    ingested_at: datetime,
    timeframe: Timeframe,
    duration: timedelta,
) -> tuple[OHLCVBar, ...]:
    bars = []
    for row in payload:
        if len(row) < 6:
            raise ValueError("Malformed Bitfinex candle")
        mts, open_, close, high, low, volume = row[:6]
        opened = datetime.fromtimestamp(int(mts) / 1000, UTC)
        bars.append(
            OHLCVBar(
                instrument_id=INSTRUMENT_ID,
                timeframe=timeframe,
                status=BarStatus.FINAL,
                open_time=opened,
                close_time=opened + duration,
                available_at=opened + duration,
                ingested_at=ingested_at,
                open=Decimal(str(open_)),
                high=Decimal(str(high)),
                low=Decimal(str(low)),
                close=Decimal(str(close)),
                volume=Decimal(str(volume)),
                source_id=SOURCE_ID,
            )
        )
    return tuple(sorted(bars, key=lambda bar: bar.open_time))


def parse_hourly(payload: list[BitfinexCandle], *, ingested_at: datetime) -> tuple[OHLCVBar, ...]:
    return _parse(
        payload,
        ingested_at=ingested_at,
        timeframe=Timeframe.ONE_HOUR,
        duration=timedelta(hours=1),
    )


def parse_daily(payload: list[BitfinexCandle], *, ingested_at: datetime) -> tuple[OHLCVBar, ...]:
    return _parse(
        payload,
        ingested_at=ingested_at,
        timeframe=Timeframe.ONE_DAY,
        duration=timedelta(days=1),
    )


def fetch_hourly(*, start: datetime, end: datetime, limit: int = 10000) -> tuple[OHLCVBar, ...]:
    query = urllib.parse.urlencode(
        {
            "start": int(start.timestamp() * 1000),
            "end": int(end.timestamp() * 1000) - 1,
            "limit": min(limit, 10000),
            "sort": 1,
        }
    )
    request = urllib.request.Request(API + "?" + query, headers=HEADERS)  # noqa: S310
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        payload = json.load(response)
    if not isinstance(payload, list):
        raise ValueError("Unexpected Bitfinex response")
    return parse_hourly(payload, ingested_at=datetime.now(UTC))


def fetch_daily(*, start: datetime, end: datetime, limit: int = 10000) -> tuple[OHLCVBar, ...]:
    """Fetch native Bitfinex daily BTC/USD candles without hourly resampling."""
    query = urllib.parse.urlencode(
        {
            "start": int(start.timestamp() * 1000),
            "end": int(end.timestamp() * 1000) - 1,
            "limit": min(limit, 10000),
            "sort": 1,
        }
    )
    request = urllib.request.Request(DAILY_API + "?" + query, headers=HEADERS)  # noqa: S310
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        payload = json.load(response)
    if not isinstance(payload, list):
        raise ValueError("Unexpected Bitfinex response")
    return parse_daily(payload, ingested_at=datetime.now(UTC))
