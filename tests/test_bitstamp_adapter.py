from __future__ import annotations

from datetime import UTC, datetime

from crypto_intelligence_os.adapters.market_data import bitstamp
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


def test_fetch_hourly_range_pages_without_duplicates(monkeypatch) -> None:
    calls = []

    def fake_fetch(*, start=None, end=None, limit=1000):
        calls.append((start, end, limit))
        base = datetime(2020, 1, 1, tzinfo=UTC)
        payload = {
            "data": {
                "ohlc": [
                    {
                        "timestamp": str(int((base.replace(hour=hour)).timestamp())),
                        "open": "100",
                        "high": "102",
                        "low": "99",
                        "close": "101",
                        "volume": "1",
                    }
                    for hour in range(4)
                    if start <= base.replace(hour=hour) < end
                ]
            }
        }
        return parse_hourly_ohlc(payload, ingested_at=datetime(2026, 1, 1, tzinfo=UTC))

    monkeypatch.setattr(bitstamp, "fetch_hourly", fake_fetch)
    start = datetime(2020, 1, 1, tzinfo=UTC)
    end = datetime(2020, 1, 1, 4, tzinfo=UTC)
    bars = bitstamp.fetch_hourly_range(start=start, end=end, page_hours=2)
    assert len(calls) == 2
    assert calls[0][1] == datetime(2020, 1, 1, 2, tzinfo=UTC)
    assert calls[1][0] == datetime(2020, 1, 1, 2, tzinfo=UTC)
    assert calls[1][1] == datetime(2020, 1, 1, 4, tzinfo=UTC)
    assert len(bars) == 4
    assert len({bar.open_time for bar in bars}) == 4


def test_fetch_hourly_range_ignores_out_of_window_boundary_rows(monkeypatch) -> None:
    base = datetime(2020, 1, 1, tzinfo=UTC)

    def fake_fetch(*, start=None, end=None, limit=1000):
        rows = []
        for hour in range(5):
            opened = base.replace(hour=hour)
            if start - bitstamp.timedelta(hours=1) <= opened <= end:
                rows.append(
                    {
                        "timestamp": str(int(opened.timestamp())),
                        "open": str(100 + hour),
                        "high": str(102 + hour),
                        "low": str(99 + hour),
                        "close": str(101 + hour),
                        "volume": "1",
                    }
                )
        return parse_hourly_ohlc(
            {"data": {"ohlc": rows}},
            ingested_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

    monkeypatch.setattr(bitstamp, "fetch_hourly", fake_fetch)
    bars = bitstamp.fetch_hourly_range(
        start=base,
        end=base.replace(hour=4),
        page_hours=2,
    )
    assert [bar.open_time for bar in bars] == [
        base.replace(hour=0),
        base.replace(hour=1),
        base.replace(hour=2),
        base.replace(hour=3),
    ]
