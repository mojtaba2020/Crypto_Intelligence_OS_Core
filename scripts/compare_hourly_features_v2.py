#!/usr/bin/env python3
"""A/B walk-forward test: legacy close-only Ridge versus OHLCV Feature V2 Ridge."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from hourly_features_v2 import feature_names, feature_vector
from train_hourly_ridge_tournament import HORIZONS, _features, _ridge_fit


def tournament(candles: list[dict[str, float]], train_min: int = 360, step: int = 24) -> dict:
    closes = [float(c["close"]) for c in candles]
    rows = []
    for horizon in HORIZONS:
        v1_err: list[float] = []
        v2_err: list[float] = []
        base_err: list[float] = []
        v1_hits = v2_hits = samples = 0
        for test_origin in range(train_min, len(candles) - horizon, step):
            origins = range(168, test_origin - horizon + 1)
            ys = [math.log(closes[o + horizon] / closes[o]) for o in origins]
            xs_v1 = [_features(closes, o) for o in origins]
            xs_v2 = [[1.0, *feature_vector(candles, o)] for o in origins]
            beta_v1 = _ridge_fit(xs_v1, ys, alpha=1.0)
            beta_v2 = _ridge_fit(xs_v2, ys, alpha=1.0)
            r1 = sum(w * v for w, v in zip(beta_v1, _features(closes, test_origin), strict=True))
            x_v2 = [1.0, *feature_vector(candles, test_origin)]
            r2 = sum(w * v for w, v in zip(beta_v2, x_v2, strict=True))
            current = closes[test_origin]
            actual = closes[test_origin + horizon]
            actual_return = math.log(actual / current)
            p1 = current * math.exp(r1)
            p2 = current * math.exp(r2)
            v1_err.append(abs(p1 - actual) / actual)
            v2_err.append(abs(p2 - actual) / actual)
            base_err.append(abs(current - actual) / actual)
            v1_hits += int((r1 >= 0) == (actual_return >= 0))
            v2_hits += int((r2 >= 0) == (actual_return >= 0))
            samples += 1
        m1 = 100 * sum(v1_err) / samples
        m2 = 100 * sum(v2_err) / samples
        mb = 100 * sum(base_err) / samples
        rows.append({
            "horizon_hours": horizon,
            "walk_forward_samples": samples,
            "v1_mape_pct": round(m1, 5),
            "v2_mape_pct": round(m2, 5),
            "persistence_mape_pct": round(mb, 5),
            "v1_direction_accuracy_pct": round(100 * v1_hits / samples, 2),
            "v2_direction_accuracy_pct": round(100 * v2_hits / samples, 2),
            "v2_beats_v1": m2 < m1,
            "v2_beats_persistence": m2 < mb,
        })
    return {
        "status": "FEATURE_V2_AB_WALK_FORWARD_RESEARCH_V1",
        "model": "ridge_same_alpha",
        "target": "future_log_return",
        "v2_feature_count": len(feature_names()),
        "v2_feature_names": list(feature_names()),
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    candles = json.loads(args.input.read_text(encoding="utf-8"))
    report = tournament(candles)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
