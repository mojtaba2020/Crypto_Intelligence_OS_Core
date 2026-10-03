#!/usr/bin/env python3
"""Deterministic feature-family ablations for Challenger V3 development/validation.

This module never accesses locked OOS. It only defines masks over the causal
point-in-time feature vector so identical walk-forward splits can compare
information families fairly.
"""
from __future__ import annotations

from scripts.multitimeframe_features_v3 import feature_names

ABLATIONS = ("baseline", "regime_only_delta", "all_features")


def feature_mask(family: str, ablation: str) -> tuple[int, ...]:
    names = feature_names(family)
    regime = tuple(
        i for i, name in enumerate(names)
        if name.startswith("trend_") or name.startswith("vol_ratio_") or name.startswith("range_position_")
    )
    baseline = tuple(i for i in range(len(names)) if i not in regime)
    if ablation == "baseline":
        return baseline
    if ablation == "regime_only_delta":
        return regime
    if ablation == "all_features":
        return tuple(range(len(names)))
    raise ValueError(f"Unknown ablation: {ablation}")


def apply_mask(row: list[float], mask: tuple[int, ...]) -> list[float]:
    if not mask:
        raise ValueError("Feature mask must not be empty")
    if max(mask) >= len(row):
        raise ValueError("Feature mask exceeds row width")
    return [row[i] for i in mask]


def ablation_manifest(family: str) -> dict[str, object]:
    names = feature_names(family)
    return {
        "family": family,
        "scope": "development_validation_only",
        "fresh_locked_oos_access": False,
        "v2_locked_oos_used_for_tuning": False,
        "ablations": {
            ablation: [names[i] for i in feature_mask(family, ablation)]
            for ablation in ABLATIONS
        },
    }
