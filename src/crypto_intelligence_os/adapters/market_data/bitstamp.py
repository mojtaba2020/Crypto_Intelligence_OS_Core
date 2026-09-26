"""Bitstamp public OHLC adapter normalized to provider-neutral OHLCVBar contracts."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from crypto_intelligence_os.market_data import BarStatus, OHLCVBar, Timeframe

API = "https://www.bitstamp.net/api/v2/ohlc"
SOURCE_ID = "source:bitstamp.public"
INSTRUMENT_ID = "market:bitstamp:spot:btc-usd"
HEADERS = {"User-Agent": "Crypto-Intelligence-OS/1.0", "Accept": "application/json"}


def parse_hourly_ohlc(payload: dict[str, Any], *, ingested_at: datetime) -> tuple[OHLCVBar, ...]:
    raw_rows = payload.get("data", {}).get("ohlc", [])
    bars = []
    for row in raw_rows:
        opened = datetime.fromtimestamp(int(row["timestamp"]), UTC)
        closed = opened + timedelta(hours=1)
        bars.append(
            OHLCVBar(
                instrument_id=INSTRUMENT_ID,
                timeframe=Timeframe.ONE_HOUR,
                status=BarStatus.FINAL,
                open_time=opened,
                close_time=closed,
                available_at=closed,
                ingested_at=ingested_at,
                open=Decimal(row["open"]),
                high=Decimal(row["high"]),
                low=Decimal(row["low"]),
                close=Decimal(row["close"]),
                volume=Decimal(row["volume"]),
                source_id=SOURCE_ID,
            )
        )
    return tuple(sorted(bars, key=lambda bar: bar.open_time))


def fetch_hourly(
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 1000,
) -> tuple[OHLCVBar, ...]:
    if not 1 <= limit <= 1000:
        raise ValueError("Bitstamp OHLC limit must be between 1 and 1000")
    query: dict[str, str | int] = {
        "step": 3600,
        "limit": limit,
        "exclude_current_candle": "true",
    }
    if start is not None:
        query["start"] = int(start.timestamp())
    if end is not None:
        query["end"] = int(end.timestamp())
    url = f"{API}/btcusd/?" + urllib.parse.urlencode(query)
    request = urllib.request.Request(url, headers=HEADERS)  # noqa: S310
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        payload = json.load(response)
    return parse_hourly_ohlc(payload, ingested_at=datetime.now(UTC))
