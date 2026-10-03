#!/usr/bin/env python3
"""Development-only statistical diagnostics for Challenger V3.

Consumes origin-level paired losses already produced by the development
tournament. It never reads fresh/locked OOS and cannot authorize promotion.
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
from pathlib import Path

try:
    from .multitimeframe_lab_v1 import SPECS
except ImportError:  # direct script execution with scripts/ on sys.path
    from multitimeframe_lab_v1 import SPECS

ALPHA = 0.05
BOOTSTRAP_REPS = 10000
SEED = 20261003


def _mbb(diffs: list[float], block: int, seed: int) -> tuple[float, list[float]]:
    n = len(diffs)
    if n < 2:
        raise ValueError("Need at least two paired forecast origins")
    b = max(1, min(block, n))
    starts = list(range(n - b + 1))
    observed = statistics.mean(diffs)
    centered = [x - observed for x in diffs]
    rng = random.Random(seed)
    boot: list[float] = []
    null: list[float] = []
    for _ in range(BOOTSTRAP_REPS):
        sample: list[float] = []
        null_sample: list[float] = []
        while len(sample) < n:
            s = rng.choice(starts)
            sample.extend(diffs[s:s + b])
            null_sample.extend(centered[s:s + b])
        boot.append(statistics.mean(sample[:n]))
        null.append(statistics.mean(null_sample[:n]))
    boot.sort()
    lo = boot[int(0.025 * BOOTSTRAP_REPS)]
    hi = boot[int(0.975 * BOOTSTRAP_REPS) - 1]
    p = (1 + sum(x >= observed for x in null)) / (BOOTSTRAP_REPS + 1)
    return p, [lo, hi]


def _holm(rows: list[dict[str, object]]) -> None:
    ordered = sorted(rows, key=lambda row: float(row["p_value"]))
    rejecting = True
    m = len(ordered)
    for rank, row in enumerate(ordered, 1):
        threshold = ALPHA / (m - rank + 1)
        reject = rejecting and float(row["p_value"]) <= threshold
        row["holm_threshold"] = threshold
        row["holm_reject"] = reject
        if not reject:
            rejecting = False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence-dir", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    spec_by_label = {s.label: s for s in SPECS}
    rows: list[dict[str, object]] = []
    for path in sorted(args.evidence_dir.glob("classical-development-*.json")):
        report = json.loads(path.read_text(encoding="utf-8"))
        for horizon, result in report.get("results", {}).items():
            spec = spec_by_label[horizon]
            for ablation in result["ablation_selected_candidates"]:
                metrics = result["ablation_metrics"][ablation]
                paired = metrics["origin_level_paired_losses"]
                candidate, cut = select_candidate(paired, tuple(metrics["candidates"].keys()))
                diffs = heldout_paired_differences(paired, candidate, cut)
                seed = SEED + sum(ord(ch) for ch in horizon + ":" + ablation + ":nested")
                p, ci = _mbb(diffs, spec.bootstrap_block_bars, seed)
                rows.append({
                    "horizon": horizon,
                    "ablation": ablation,
                    "candidate": candidate,
                    "selection_samples": cut,
                    "samples": len(diffs),
                    "selection_method": "earlier_origins_only",
                    "diagnostic_method": "later_origins_only",
                    "model_mape": metrics["candidates"][candidate]["mape"],
                    "persistence_mape": metrics["persistence_mape"],
                    "mean_loss_improvement": statistics.mean(diffs),
                    "improvement_ci95": ci,
                    "p_value": p,
                })

    _holm(rows)
    for row in rows:
        row["diagnostic_pass"] = bool(
            float(row["mean_loss_improvement"]) > 0
            and float(row["improvement_ci95"][0]) > 0
            and row["holm_reject"]
        )

    output = {
        "status": "CHALLENGER_V3_NESTED_DEVELOPMENT_STATISTICAL_DIAGNOSTICS_ONLY",
        "confirmatory": False,
        "fresh_locked_oos_access": False,
        "production_promotion": False,
        "bootstrap": {"method": "moving_block", "repetitions": BOOTSTRAP_REPS, "seed_base": SEED},
        "multiplicity": {"method": "holm_bonferroni", "alpha": ALPHA, "family": "all_evaluated_horizon_x_ablation_nested_winners"},
        "results": rows,
        "selection_bias_control": "candidate selected on earlier origins; statistics computed only on later origins",\n        "interpretation": "Nested hypothesis-strength diagnostics only; passing does not authorize freeze or promotion.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
