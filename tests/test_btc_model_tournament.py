"""Chronological tournament unit tests."""
import sqlite3
from datetime import date, timedelta

import pytest
from scripts.evaluate_btc_model_tournament import MODELS, predict, run


def test_fixed_models_use_only_history():
    prices = [100.0 + i for i in range(200)]
    assert predict("persistence", prices, 150, 7) == 250.0
    before = {name: predict(name, prices, 150, 7) for name in MODELS}
    prices[151:] = [1_000_000.0] * 49
    assert before == {name: predict(name, prices, 150, 7) for name in MODELS}


def test_tournament_has_seven_nonempty_locked_splits(tmp_path):
    db = tmp_path / "prices.sqlite"
    start = date(2011, 1, 1)
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE daily_price (day TEXT, price_usd REAL)")
        connection.executemany(
            "INSERT INTO daily_price VALUES (?, ?)",
            ((str(start + timedelta(days=i)), 100 + i * 0.1) for i in range(5800)),
        )
    report = run(db)
    assert len(report["results"]) == 7
    for row in report["results"]:
        assert row["validation_examples"] > 0
        assert row["locked_test_examples"] > 0
        assert row["selected_on_validation"] in MODELS
        assert row["selected_test_mae_usd"] >= 0


def test_rejects_no_locked_test(tmp_path):
    db = tmp_path / "prices.sqlite"
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE daily_price (day TEXT, price_usd REAL)")
        connection.execute("INSERT INTO daily_price VALUES ('2011-01-01', 100)")
    with pytest.raises(ValueError):
        run(db)
