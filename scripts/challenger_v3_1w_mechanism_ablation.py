#!/usr/bin/env python3
"""Predeclared mechanism ablation for the 1w Elastic Net research lead.

Development/validation only. Tests three bounded hypotheses: the seventh regime
feature, L1/L2 mixing, and regime stability. No locked OOS or production use.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path

from sklearn.linear_model import ElasticNet, Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    from scripts.challenger_v3_feature_ablation import apply_mask, feature_mask
    from scripts.multitimeframe_features_v3 import (
        feature_names,
        feature_vector,
        is_temporally_valid_sample,
    )
    from scripts.multitimeframe_split_v1 import chronological_split
except ModuleNotFoundError:
    from challenger_v3_feature_ablation import apply_mask, feature_mask
    from multitimeframe_features_v3 import (
        feature_names,
        feature_vector,
        is_temporally_valid_sample,
    )
    from multitimeframe_split_v1 import chronological_split

SEED = 20260929
CONFIGS = (
    ("ridge_control", None),
    ("elastic_l1_0", 0.0),
    ("elastic_l1_025", 0.25),
    ("elastic_l1_050", 0.50),
    ("elastic_l1_075", 0.75),
    ("elastic_l1_100", 1.0),
)
SUBSETS = ("regime_7", "stable_6")


def _fit(name, l1, x, y):
    if name == "ridge_control":
        m = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
    else:
        m = make_pipeline(
            StandardScaler(),
            ElasticNet(alpha=0.0001, l1_ratio=l1, max_iter=5000, random_state=SEED),
        )
    m.fit(x, y)
    return m


def _subset_indices(kind):
    names = feature_names("weekly")
    regime = feature_mask("weekly", "regime_only_delta")
    if kind == "regime_7":
        return regime
    excluded = "range_position_13"
    return [i for i in regime if names[i] != excluded]


def run(candles):
    split = chronological_split(len(candles), 260, 1)
    view = candles[: split.validation_end]
    valid = [
        i for i in range(52, len(view) - 1) if is_temporally_valid_sample(view, "weekly", i, 1)
    ]
    origins = [
        i for i in range(312, len(view) - 1, 4) if is_temporally_valid_sample(view, "weekly", i, 1)
    ]
    labels = {i: math.log(float(view[i + 1]["close"]) / float(view[i]["close"])) for i in valid}
    rows = []
    for subset in SUBSETS:
        idx = _subset_indices(subset)
        cache = {i: apply_mask(feature_vector(view, i, "weekly"), idx) for i in valid}
        for name, l1 in CONFIGS:
            improvements = []
            model_errors = []
            base_errors = []
            period_rows = []
            for origin in origins:
                train = [i for i in valid if i < origin and i + 1 <= origin]
                model = _fit(name, l1, [cache[i] for i in train], [labels[i] for i in train])
                current = float(view[origin]["close"])
                actual = float(view[origin + 1]["close"])
                pred = current * math.exp(float(model.predict([cache[origin]])[0]))
                be = abs(current - actual) / actual
                me = abs(pred - actual) / actual
                base_errors.append(be)
                model_errors.append(me)
                improvements.append(be - me)
                period_rows.append((origin, be - me))
            n = len(improvements)
            third = max(1, n // 3)
            thirds = [
                improvements[:third],
                improvements[third : 2 * third],
                improvements[2 * third :],
            ]
            rows.append(
                {
                    "subset": subset,
                    "model": name,
                    "l1_ratio": l1,
                    "samples": n,
                    "persistence_mape": statistics.fmean(base_errors),
                    "model_mape": statistics.fmean(model_errors),
                    "mean_improvement": statistics.fmean(improvements),
                    "median_improvement": statistics.median(improvements),
                    "win_fraction": statistics.fmean(x > 0 for x in improvements),
                    "chronological_third_improvements": [statistics.fmean(x) for x in thirds if x],
                    "all_thirds_positive": all(statistics.fmean(x) > 0 for x in thirds if x),
                }
            )
    return rows


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    candles = json.loads(Path(a.data).read_text())
    report = {
        "status": "CHALLENGER_V3_1W_MECHANISM_ABLATION_DEVELOPMENT_ONLY",
        "scope": "development_validation_only",
        "predeclared_hypotheses": [
            "range_position_13 materially contributes beyond the stable six",
            "Elastic Net L1/L2 mixing outperforms pure L2-like and pure L1 controls",
            "any apparent advantage remains directionally stable across chronological thirds",
        ],
        "selection_policy": (
            "diagnostic explanation only; no hyperparameter winner may be frozen "
            "from this experiment"
        ),
        "fresh_locked_oos_access": False,
        "v2_locked_oos_used_for_tuning": False,
        "confirmatory": False,
        "production_eligible": False,
        "results": run(candles),
    }
    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"], "rows": len(report["results"])}))


if __name__ == "__main__":
    main()
