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


def fetch_hourly_range(
    *,
    start: datetime,
    end: datetime,
    page_hours: int = 1000,
) -> tuple[OHLCVBar, ...]:
    """Fetch a long closed-candle range in deterministic non-overlapping pages."""
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("start and end must be timezone-aware")
    if start >= end:
        raise ValueError("start must be earlier than end")
    if not 1 <= page_hours <= 1000:
        raise ValueError("page_hours must be between 1 and 1000")

    cursor = start
    collected: dict[datetime, OHLCVBar] = {}
    while cursor < end:
        page_end = min(end, cursor + timedelta(hours=page_hours))
        page = fetch_hourly(start=cursor, end=page_end, limit=page_hours)
        for bar in page:
            if start <= bar.open_time < end:
                existing = collected.get(bar.open_time)
                if existing is not None and existing.model_dump(
                    exclude={"ingested_at"}
                ) != bar.model_dump(exclude={"ingested_at"}):
                    raise ValueError(
                        f"Bitstamp returned conflicting candle at {bar.open_time.isoformat()}"
                    )
                collected[bar.open_time] = bar
        cursor = page_end

    return tuple(collected[key] for key in sorted(collected))
