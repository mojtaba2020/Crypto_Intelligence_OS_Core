from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from crypto_intelligence_os.adapters.market_data.historical_archive import (
    HistoricalOHLCVArchive,
    canonical_bar_fingerprint,
    validate_hourly_continuity,
)
from crypto_intelligence_os.market_data import BarStatus, OHLCVBar, Timeframe


def bar(hour: int, *, source: str = "source:test.history", close: str = "101") -> OHLCVBar:
    opened = datetime(2020, 1, 1, tzinfo=UTC) + timedelta(hours=hour)
    closed = opened + timedelta(hours=1)
    return OHLCVBar(
        instrument_id="market:test:spot:btc-usd",
        timeframe=Timeframe.ONE_HOUR,
        status=BarStatus.FINAL,
        open_time=opened,
        close_time=closed,
        available_at=closed,
        ingested_at=datetime(2026, 1, 1, tzinfo=UTC),
        open=Decimal("100"),
        high=Decimal("102"),
        low=Decimal("99"),
        close=Decimal(close),
        volume=Decimal("5"),
        source_id=source,
    )


def test_archive_is_idempotent(tmp_path: Path) -> None:
    with HistoricalOHLCVArchive(tmp_path / "history.sqlite") as archive:
        assert archive.persist((bar(0), bar(1))) == 2
        assert archive.persist((bar(0), bar(1))) == 0
        assert archive.count() == 2


def test_archive_keeps_sources_separate(tmp_path: Path) -> None:
    with HistoricalOHLCVArchive(tmp_path / "history.sqlite") as archive:
        assert (
            archive.persist(
                (
                    bar(0),
                    bar(0, source="source:test.second"),
                )
            )
            == 2
        )
        assert archive.count() == 2


def test_archive_rejects_silent_revision(tmp_path: Path) -> None:
    original = bar(0)
    revised = original.model_copy(update={"close": Decimal("100.5")})
    with HistoricalOHLCVArchive(tmp_path / "history.sqlite") as archive:
        archive.persist((original,))
        with pytest.raises(ValueError, match="revision"):
            archive.persist((revised,))


def test_hourly_continuity_accepts_exact_spacing() -> None:
    validate_hourly_continuity((bar(0), bar(1), bar(2)))


def test_hourly_continuity_rejects_gap() -> None:
    with pytest.raises(ValueError, match="continuity gap"):
        validate_hourly_continuity((bar(0), bar(2)))


def test_hourly_continuity_rejects_mixed_sources() -> None:
    with pytest.raises(ValueError, match="one source"):
        validate_hourly_continuity((bar(0), bar(1, source="source:test.second")))


def test_canonical_fingerprint_ignores_ingestion_metadata() -> None:
    original = bar(0)
    reingested = original.model_copy(
        update={
            "bar_id": "bar_different_internal_id",
            "ingested_at": datetime(2026, 2, 1, tzinfo=UTC),
        }
    )
    assert canonical_bar_fingerprint((original,)) == canonical_bar_fingerprint((reingested,))


def test_canonical_fingerprint_changes_when_market_observation_changes() -> None:
    original = bar(0)
    revised = original.model_copy(update={"close": Decimal("100.5")})
    assert canonical_bar_fingerprint((original,)) != canonical_bar_fingerprint((revised,))
