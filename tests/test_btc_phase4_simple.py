"""Contract tests for fixed, matched-origin phase 4 forecasts."""

import sqlite3
from datetime import date, timedelta

import pytest
from scripts.evaluate_btc_phase4_simple import evaluate


def _archive(tmp_path, days=1100, gap=None):
    path = tmp_path / "history.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE daily_price (day TEXT, price_usd REAL)")
        connection.executemany(
            "INSERT INTO daily_price VALUES (?, ?)",
            [
                (
                    (date(2011, 1, 1) + timedelta(days=index)).isoformat(),
                    10000.0 + index * 10,
                )
                for index in range(days)
                if index != gap
            ],
        )
    return path


def test_phase4_fixed_candidates_share_all_origins(tmp_path):
    result = evaluate(_archive(tmp_path), horizon=7, step=7, holdout_days=365)
    assert result["test_examples"] > 0
    assert set(result["mae_usd"]) == {
        "persistence",
        "momentum_30d_quarter",
        "momentum_30d_half",
        "momentum_90d_quarter",
    }
    for row in result["paired_vs_persistence"].values():
        assert row["lower_error_count"] + row["higher_error_count"] <= result["test_examples"]


def test_phase4_rejects_missing_day(tmp_path):
    with pytest.raises(ValueError, match="Missing daily close"):
        evaluate(_archive(tmp_path, gap=400), horizon=7, step=7, holdout_days=365)


def test_phase4_rejects_unresolved_test_window(tmp_path):
    with pytest.raises(ValueError, match="No resolved"):
        evaluate(_archive(tmp_path, days=370), horizon=30, step=7, holdout_days=365)
