"""Offline Bitfinex adapter contract tests."""

from datetime import UTC, datetime

import pytest

from crypto_intelligence_os.adapters.market_data.bitfinex import SOURCE_ID, parse_daily, parse_hourly
from crypto_intelligence_os.market_data import Timeframe


def test_parse_hourly_normalizes_and_sorts():
    now = datetime(2026, 9, 28, tzinfo=UTC)
    payload = [[3600000, 101, 102, 103, 100, 5], [0, 100, 101, 102, 99, 4]]
    bars = parse_hourly(payload, ingested_at=now)
    assert len(bars) == 2
    assert bars[0].open_time.timestamp() == 0
    assert bars[0].source_id == SOURCE_ID
    assert float(bars[1].close) == 102


def test_parse_hourly_rejects_malformed():
    now = datetime(2026, 9, 28, tzinfo=UTC)
    with pytest.raises(ValueError, match="Malformed Bitfinex candle"):
        parse_hourly([[0, 100]], ingested_at=now)


def test_parse_daily_uses_daily_contract():
    now = datetime(2026, 9, 28, tzinfo=UTC)
    bars = parse_daily([[0, 100, 101, 102, 99, 4]], ingested_at=now)
    assert bars[0].timeframe is Timeframe.ONE_DAY
    assert (bars[0].close_time - bars[0].open_time).days == 1
