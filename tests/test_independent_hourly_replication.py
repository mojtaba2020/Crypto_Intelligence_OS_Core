"""Offline tests for independent exchange replication evaluator."""
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from scripts.evaluate_independent_hourly_replication import evaluate

from crypto_intelligence_os.adapters.market_data.historical_archive import (
    HistoricalOHLCVArchive,
)
from crypto_intelligence_os.market_data import BarStatus, OHLCVBar, Timeframe


def test_replication_is_fail_closed_and_complete(tmp_path):
    source = "source:test"
    instrument = "market:test:btc-usd"
    start = datetime(2026, 1, 1, tzinfo=UTC)
    bars = []
    price = 10000.0
    for index in range(360):
        price *= 1.0002
        opened = start + timedelta(hours=index)
        bars.append(
            OHLCVBar(
                instrument_id=instrument,
                timeframe=Timeframe.ONE_HOUR,
                status=BarStatus.FINAL,
                open_time=opened,
                close_time=opened + timedelta(hours=1),
                available_at=opened + timedelta(hours=1),
                ingested_at=opened + timedelta(hours=1),
                open=Decimal(str(price)),
                high=Decimal(str(price * 1.001)),
                low=Decimal(str(price * 0.999)),
                close=Decimal(str(price)),
                volume=Decimal("1"),
                source_id=source,
            )
        )
    database = tmp_path / "x.sqlite"
    with HistoricalOHLCVArchive(database) as archive:
        archive.persist(tuple(bars))
    output = evaluate(database, source, instrument, "ridge", step=2)
    assert output["automatic_promotion"] is False
    assert {row["horizon_hours"] for row in output["rows"]} == {1, 2, 3, 4, 12}
    assert all(
        "one_sided_null_centered_p_value" in row["statistical_gate"]
        for row in output["rows"]
    )
