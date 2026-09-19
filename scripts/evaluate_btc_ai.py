#!/usr/bin/env python3
"""Train and evaluate BTC baseline against an existing daily SQLite archive.

Run only on a trusted local copy of data/btc_usd_daily.sqlite. This script does
not fetch prices or claim a model is trained until actual archive execution.
"""

from __future__ import annotations

import argparse
import json
from datetime import timedelta
from pathlib import Path

from crypto_intelligence_os.adapters.market_data.btc_archive import BTCArchive
from crypto_intelligence_os.ai_forecasting import Observation, predict, walk_forward
from crypto_intelligence_os.market_data import BarStatus, Timeframe


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--horizon-days", type=int, default=7)
    arguments = parser.parse_args()
    if not arguments.archive.is_file():
        parser.error(f"Archive not found: {arguments.archive}")
    with BTCArchive(arguments.archive) as archive:
        archive.integrity_check()
        bars = archive.all_bars()
    if not bars:
        raise ValueError("Archive has no candles")
    if any(
        bar.timeframe is not Timeframe.ONE_DAY or bar.status is not BarStatus.FINAL
        for bar in bars
    ):
        raise ValueError("Archive must contain final daily candles only")
    instruments = {bar.instrument_id for bar in bars}
    sources = {bar.source_id for bar in bars}
    if len(instruments) != 1 or len(sources) != 1:
        raise ValueError("Do not combine distinct instruments or price sources")
    observations = tuple(Observation(bar.open_time.date(), float(bar.close)) for bar in bars)
    evaluation = walk_forward(observations, horizon_days=arguments.horizon_days)
    forecast = predict(evaluation.model, observations)
    result = {
        "status": "EVALUATED_ON_ARCHIVE",
        "source": next(iter(sources)),
        "instrument": next(iter(instruments)),
        "first_day": observations[0].day.isoformat(),
        "last_completed_day": observations[-1].day.isoformat(),
        "forecast_target_day": (
            observations[-1].day + timedelta(days=arguments.horizon_days)
        ).isoformat(),
        "forecast_price_usd": forecast,
        "horizon_days": arguments.horizon_days,
        "train_examples": evaluation.train_examples,
        "test_examples": evaluation.test_examples,
        "model_mae_usd": evaluation.model_mae,
        "persistence_mae_usd": evaluation.persistence_mae,
        "model_mape_pct": evaluation.model_mape_pct,
        "persistence_mape_pct": evaluation.persistence_mape_pct,
        "warning": "Research baseline only; short history is not cycle validation.",
    }
    arguments.report.parent.mkdir(parents=True, exist_ok=True)
    arguments.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "
")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
