"""Offline Bitfinex adapter contract tests."""
from datetime import UTC, datetime
from crypto_intelligence_os.adapters.market_data.bitfinex import parse_hourly, SOURCE_ID

def test_parse_hourly_normalizes_and_sorts():
    now=datetime(2026,9,28,tzinfo=UTC)
    payload=[[3600000,101,102,103,100,5],[0,100,101,102,99,4]]
    bars=parse_hourly(payload,ingested_at=now)
    assert len(bars)==2
    assert bars[0].open_time.timestamp()==0
    assert bars[0].source_id==SOURCE_ID
    assert float(bars[1].close)==102
