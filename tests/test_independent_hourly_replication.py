"""Offline tests for independent exchange replication evaluator."""
from datetime import UTC,datetime,timedelta
from decimal import Decimal
from crypto_intelligence_os.market_data import OHLCVBar,BarStatus,Timeframe
from crypto_intelligence_os.adapters.market_data.historical_archive import HistoricalOHLCVArchive
from scripts.evaluate_independent_hourly_replication import evaluate

def test_replication_is_fail_closed_and_complete(tmp_path):
    source="source:test"; instrument="market:test:btc-usd"; start=datetime(2026,1,1,tzinfo=UTC)
    bars=[]
    price=10000.0
    for i in range(360):
        price*=1.0002
        t=start+timedelta(hours=i)
        bars.append(OHLCVBar(instrument_id=instrument,timeframe=Timeframe.ONE_HOUR,status=BarStatus.FINAL,open_time=t,close_time=t+timedelta(hours=1),available_at=t+timedelta(hours=1),ingested_at=t+timedelta(hours=1),open=Decimal(str(price)),high=Decimal(str(price*1.001)),low=Decimal(str(price*.999)),close=Decimal(str(price)),volume=Decimal("1"),source_id=source))
    db=tmp_path/"x.sqlite"
    with HistoricalOHLCVArchive(db) as a: a.persist(tuple(bars))
    out=evaluate(db,source,instrument,"ridge",step=2)
    assert out["automatic_promotion"] is False
    assert {r["horizon_hours"] for r in out["rows"]}=={1,2,3,4,12}
    assert all("one_sided_null_centered_p_value" in r["statistical_gate"] for r in out["rows"])
