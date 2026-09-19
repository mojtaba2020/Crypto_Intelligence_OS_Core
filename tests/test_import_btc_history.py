"""Validate historical importer without downloading remote data."""

import sqlite3
from datetime import date

import pytest
from scripts.import_btc_history import import_history


def test_import_preserves_missing_days_and_provenance(tmp_path):
    csv_text = "time,PriceUSD\n2011-01-01,0.30\n2011-01-03,0.31\n"
    target = tmp_path / "history.sqlite"
    report = import_history(csv_text, target, cutoff=date(2011, 1, 3))
    assert report["rows"] == 2
    assert report["missing_ranges"] == [{"start": "2011-01-02", "end": "2011-01-02"}]
    with sqlite3.connect(target) as connection:
        assert connection.execute("SELECT COUNT(*) FROM daily_price").fetchone()[0] == 2
        assert connection.execute(
            "SELECT value FROM provenance WHERE key = 'metric'"
        ).fetchone()[0] == "BTC PriceUSD daily aggregate; not Coinbase OHLCV"


def test_import_rejects_invalid_prices(tmp_path):
    with pytest.raises(ValueError, match="nonpositive"):
        import_history(
            "time,PriceUSD\n2011-01-01,0\n",
            tmp_path / "invalid.sqlite",
            cutoff=date(2011, 1, 1),
        )
