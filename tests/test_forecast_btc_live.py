"""Offline checks for the timestamped numerical forecast prototype."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from scripts import forecast_btc_live as live


def test_forecast_models() -> None:
    origin = 100 * 86400
    prices = {origin - i * 86400: 100.0 - i for i in range(90)}
    assert live.forecast("persistence", 110.0, prices, origin, 7, 86400) == 110.0
    assert live.forecast("momentum_30d_quarter", 110.0, prices, origin, 30, 86400) == 119.75
    with pytest.raises(ValueError, match="Daily momentum"):
        live.forecast("momentum_30d_quarter", 110.0, prices, origin, 1, 3600)
    with pytest.raises(ValueError, match="Unknown model"):
        live.forecast("unrecognized", 110.0, prices, origin, 1, 86400)


def test_run_offline_with_mock_market(tmp_path: Path) -> None:
    now = datetime(2026, 9, 24, 12, 30, tzinfo=UTC)
    selection = {
        "status": "MODEL_TOURNAMENT_RESEARCH_ONLY",
        "results": [
            {
                "horizon_days": horizon,
                "selected_on_validation": "momentum_30d_quarter" if horizon == 3 else "persistence",
                "locked_test_examples": 10,
                "selected_test_improvement_vs_persistence_pct": 0,
            }
            for horizon in live.DAILY_HORIZONS
        ],
    }
    report = tmp_path / "selection.json"
    report.write_text(json.dumps(selection), encoding="utf-8")

    def market(path: str) -> object:
        if path.endswith("/ticker"):
            return {"price": "100000", "time": now.isoformat()}
        granularity = 86400 if "granularity=86400" in path else 3600
        end = int(now.timestamp()) // granularity * granularity
        return [[end - i * granularity, 1, 1, 1, 100000 - i, 1] for i in range(1, 201)]

    with patch.object(live, "fetch_json", side_effect=market):
        output = live.run(report, now)
    assert output["spot_price_usd"] == 100000
    assert len(output["forecasts"]) == 14
    assert output["forecasts"][0]["evidence"] == "UNVALIDATED_HOURLY_BASELINE"
    daily_three = next(row for row in output["forecasts"] if row["timeframe"] == "3d")
    assert daily_three["predicted_price_usd"] > 100000
    assert daily_three["model"] == "momentum_30d_quarter"


def test_stale_ticker_rejected(tmp_path: Path) -> None:
    report = tmp_path / "selection.json"
    report.write_text(json.dumps({"status": "MODEL_TOURNAMENT_RESEARCH_ONLY", "results": [
        {"horizon_days": h} for h in live.DAILY_HORIZONS
    ]}), encoding="utf-8")
    with patch.object(live, "fetch_json", return_value={
        "price": "100000", "time": "2026-09-23T00:00:00Z"
    }):
        with pytest.raises(ValueError, match="stale"):
            live.run(report, datetime(2026, 9, 24, 12, 30, tzinfo=UTC))
