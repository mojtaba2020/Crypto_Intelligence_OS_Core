#!/usr/bin/env python3
"""Pre-specified point-in-time regime gate for locked OOS evidence."""

from __future__ import annotations

import math
import statistics

from scripts.multitimeframe_features_v3 import WINDOWS

REGIMES = ("uptrend", "downtrend", "high_volatility", "low_volatility")


def classify_regimes(
    candles: list[dict[str, float]],
    origin: int,
    family: str,
) -> tuple[str, str]:
    """Classify trend and volatility using information available at origin only."""
    longest = max(WINDOWS[family])
    if origin < longest or origin >= len(candles):
        raise ValueError("Regime origin lacks required completed history")
    close = float(candles[origin]["close"])
    anchor = float(candles[origin - longest]["close"])
    if close <= 0 or anchor <= 0:
        raise ValueError("Close must be positive")
    trend = "uptrend" if close >= anchor else "downtrend"

    returns = [
        math.log(float(candles[i]["close"]) / float(candles[i - 1]["close"]))
        for i in range(origin - longest + 1, origin + 1)
    ]
    recent_window = max(3, longest // 4)
    recent_vol = statistics.pstdev(returns[-recent_window:])
    historical_vols = [
        statistics.pstdev(returns[i - recent_window : i])
        for i in range(recent_window, len(returns) + 1)
    ]
    threshold = statistics.median(historical_vols)
    volatility = "high_volatility" if recent_vol >= threshold else "low_volatility"
    return trend, volatility


def regime_gate(
    candles: list[dict[str, float]],
    origins: list[int],
    challenger_losses: list[float],
    baseline_losses: list[float],
    family: str,
    *,
    minimum_samples: int = 8,
) -> dict[str, object]:
    """Report pre-specified subgroup evidence without selecting a favorable subgroup."""
    if not (len(origins) == len(challenger_losses) == len(baseline_losses)):
        raise ValueError("Regime inputs must have identical lengths")
    if minimum_samples < 2:
        raise ValueError("minimum_samples must be at least 2")
    buckets: dict[str, list[float]] = {name: [] for name in REGIMES}
    for origin, challenger, baseline in zip(
        origins, challenger_losses, baseline_losses, strict=True
    ):
        trend, volatility = classify_regimes(candles, origin, family)
        improvement = baseline - challenger
        buckets[trend].append(improvement)
        buckets[volatility].append(improvement)

    reports: dict[str, dict[str, object]] = {}
    for name in REGIMES:
        values = buckets[name]
        enough = len(values) >= minimum_samples
        reports[name] = {
            "samples": len(values),
            "mean_improvement": statistics.mean(values) if values else None,
            "enough_samples": enough,
            "positive_mean": enough and statistics.mean(values) > 0.0,
        }
    return {
        "policy": "pre_specified_descriptive_gate_no_subgroup_selection",
        "regimes": reports,
        "all_regimes_sufficient": all(report["enough_samples"] for report in reports.values()),
        "production_promotion": False,
    }
