"""Coverage manifest tests: unknown is not zero and horizons are not candle inputs."""
import json
from pathlib import Path

from scripts.report_timeframe_coverage import build


def test_missing_inputs_are_unverified(tmp_path: Path) -> None:
    report = build(tmp_path)
    assert len(report["coverage"]) == 13
    assert all(row["status"] == "not_verified" for row in report["coverage"])


def test_counts_and_input_horizon_separation(tmp_path: Path) -> None:
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/btc_hourly_prospective.py").write_text("")
    (tmp_path / "scripts/btc_phase5_prospective.py").write_text("")
    (tmp_path / "research").mkdir()
    (tmp_path / "research/hourly_forecasts.jsonl").write_text(
        json.dumps({"version": "v", "origin_hour_utc": "2026-09-21T00:00:00+00:00", "horizon_hours": 4}) + "\n"
    )
    (tmp_path / "research/hourly_scores.jsonl").write_text(
        json.dumps({"version": "v", "origin_hour_utc": "2026-09-21T00:00:00+00:00", "horizon_hours": 4}) + "\n"
    )
    (tmp_path / "research/phase5_forecasts.jsonl").write_text(
        json.dumps({"version": "v", "origin_day": "2026-09-21", "horizon_days": 3}) + "\n"
    )
    rows = build(tmp_path)["coverage"]
    hourly = next(r for r in rows if r["input_candle"] == "1h" and r["forecast_horizon"] == "4h")
    daily = next(r for r in rows if r["input_candle"] == "1d" and r["forecast_horizon"] == "3d")
    assert (hourly["issued_count"], hourly["resolved_count"], hourly["status"]) == (1, 1, "resolved_and_scored")
    assert (daily["issued_count"], daily["resolved_count"]) == (1, None)
    assert next(r for r in rows if r["input_candle"] == "4h")["status"] == "not_verified"
