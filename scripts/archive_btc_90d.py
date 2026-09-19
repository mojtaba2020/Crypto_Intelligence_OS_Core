#!/usr/bin/env python3
"""Archive 90 validated, final daily BTC/USD bars from public Coinbase market data.

The archive records today's ingestion time; it does not claim that this system observed
the historical candles when they originally closed. No authentication or trades.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from crypto_intelligence_os.adapters.market_data import (
    COINBASE_BTC_USD,
    COINBASE_SOURCE_ID,
    CoinbasePublicCandleSource,
)
from crypto_intelligence_os.market_data import BarStatus, OHLCVBar, Timeframe


def validate_daily_bars(
    bars: tuple[OHLCVBar, ...], *, start: datetime, end: datetime, cutoff: datetime
) -> None:
    """Reject missing, duplicate, incomplete, wrong-source, or future daily candles."""
    expected_days = (end - start).days
    if len(bars) != expected_days:
        raise ValueError(f"Expected {expected_days} daily bars, received {len(bars)}")
    for index, bar in enumerate(bars):
        expected_open = start + timedelta(days=index)
        if (
            bar.open_time != expected_open
            or bar.close_time != expected_open + timedelta(days=1)
            or bar.instrument_id != COINBASE_BTC_USD.instrument_id
            or bar.source_id != COINBASE_SOURCE_ID
            or bar.timeframe is not Timeframe.ONE_DAY
            or bar.status is not BarStatus.FINAL
            or bar.available_at > cutoff
            or bar.ingested_at < bar.available_at
        ):
            raise ValueError(f"Invalid, missing, or future BTC daily bar at {expected_open}")


def main() -> int:
    source = CoinbasePublicCandleSource()
    source_time = source.fetch_server_time()
    end = source_time.replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=90)
    bars = source.fetch_final_bars(
        timeframe=Timeframe.ONE_DAY,
        start=start,
        end=end,
        as_of=source_time,
    )
    validate_daily_bars(bars, start=start, end=end, cutoff=source_time)
    recorded_at = max(datetime.now(UTC), *(bar.ingested_at for bar in bars))
    payload = {
        "archive_version": "1.0",
        "provider": COINBASE_SOURCE_ID,
        "instrument": COINBASE_BTC_USD.model_dump(mode="json"),
        "timeframe": Timeframe.ONE_DAY.value,
        "knowledge_mode": "SYSTEM_KNOWN",
        "historical_knowledge_warning": (
            "Historical candle values were retrieved now, not observed by this system "
            "at their historical close times."
        ),
        "start_inclusive": start.isoformat(),
        "end_exclusive": end.isoformat(),
        "source_server_time": source_time.isoformat(),
        "recorded_at": recorded_at.isoformat(),
        "bar_count": len(bars),
        "bars": [bar.model_dump(mode="json") for bar in bars],
    }
    destination = Path("btc_usd_90d.json")
    data = (json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode()
    destination.write_bytes(data)
    checksum = hashlib.sha256(data).hexdigest()
    Path("btc_usd_90d.sha256").write_text(f"{checksum}  {destination.name}\n")
    print(
        f"VALIDATED: {len(bars)} consecutive FINAL daily BTC/USD bars from "
        f"{start.isoformat()} to {end.isoformat()}; SHA-256: {checksum}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
