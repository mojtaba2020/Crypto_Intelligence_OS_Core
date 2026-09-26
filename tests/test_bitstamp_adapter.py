from __future__ import annotations

from datetime import UTC, datetime

from crypto_intelligence_os.adapters.market_data.bitstamp import (
    INSTRUMENT_ID,
    SOURCE_ID,
    parse_hourly_ohlc,
)
from crypto_intelligence_os.market_data import BarStatus, Timeframe


def test_parse_hourly_ohlc_normalizes_bitstamp_payload() -> None:
    payload = {
        "data": {
            "pair": "BTC/USD",
            "ohlc": [
                {
                    "timestamp": "1643630400",
                    "open": "2188.97",
                    "high": "2211.00",
                    "low": "2180.00",
                    "close": "2200.00",
                    "volume": "4.01560417",
                }
            ],
        }
    }
    ingested = datetime(2026, 1, 1, tzinfo=UTC)
    bars = parse_hourly_ohlc(payload, ingested_at=ingested)
    assert len(bars) == 1
    bar = bars[0]
    assert bar.instrument_id == INSTRUMENT_ID
    assert bar.source_id == SOURCE_ID
    assert bar.timeframe is Timeframe.ONE_HOUR
    assert bar.status is BarStatus.FINAL
    assert bar.close_time > bar.open_time
    assert bar.available_at == bar.close_time
    assert bar.ingested_at == ingested


def test_parse_hourly_ohlc_sorts_oldest_first() -> None:
    payload = {
        "data": {
            "ohlc": [
                {
                    "timestamp": "7200",
                    "open": "101",
                    "high": "102",
                    "low": "100",
                    "close": "101",
                    "volume": "1",
                },
                {
                    "timestamp": "3600",
                    "open": "100",
                    "high": "101",
                    "low": "99",
                    "close": "100",
                    "volume": "1",
                },
            ]
        }
    }
    bars = parse_hourly_ohlc(payload, ingested_at=datetime(2026, 1, 1, tzinfo=UTC))
    assert bars[0].open_time < bars[1].open_time
