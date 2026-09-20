"""Synthetic contract tests for paired Coinbase volume ablation."""

import sqlite3
from datetime import date, timedelta

import pytest
from scripts.evaluate_btc_volume_ablation import evaluate


def _database(tmp_path, *, days=850, gap=None):
    path = tmp_path / "coinbase.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE coinbase_ohlcv (day TEXT PRIMARY KEY, close REAL, volume_btc REAL)"
        )
        connection.executemany(
            "INSERT INTO coinbase_ohlcv VALUES (?, ?, ?)",
            [
                (
                    (date(2023, 1, 1) + timedelta(days=index)).isoformat(),
                    10000.0 + index * 10,
                    100.0 + index % 17,
                )
                for index in range(days)
                if index != gap
            ],
        )
    return path


def test_paired_volume_uses_identical_origins_and_past_labels(tmp_path):
    report = evaluate(_database(tmp_path), horizon=7, step=60)
    assert report["test_examples"] > 0
    assert (
        report["volume_lower_error_count"]
        + report["volume_higher_error_count"]
        + report["volume_equal_error_count"]
        == report["test_examples"]
    )
    assert set(report["mae_usd"]) == {"price_only", "price_plus_volume", "persistence"}


def test_volume_history_gap_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="contiguous"):
        evaluate(_database(tmp_path, gap=400), horizon=7, step=60)


def test_volume_requires_sufficient_past_only_history(tmp_path):
    with pytest.raises(ValueError, match="Insufficient"):
        evaluate(_database(tmp_path, days=500), horizon=30, step=60)
