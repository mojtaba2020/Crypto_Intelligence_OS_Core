#!/usr/bin/env python3
"""Fetch a small read-only BTC/USD sample from Coinbase public market data."""

from __future__ import annotations

import json
from datetime import timedelta

from crypto_intelligence_os.adapters.market_data import CoinbasePublicCandleSource
from crypto_intelligence_os.market_data import Timeframe


def main() -> int:
    source = CoinbasePublicCandleSource()
    server_time = source.fetch_server_time()
    bars = source.fetch_final_bars(
        timeframe=Timeframe.ONE_HOUR,
        start=server_time - timedelta(hours=6),
        end=server_time,
        as_of=server_time,
    )
    payload = {
        "source_time": server_time.isoformat(),
        "bar_count": len(bars),
        "bars": [bar.model_dump(mode="json") for bar in bars[-3:]],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
