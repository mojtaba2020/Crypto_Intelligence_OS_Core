from __future__ import annotations

import pytest

from scripts.challenger_v3_feature_ablation import (
    ABLATIONS,
    ablation_manifest,
    apply_mask,
    feature_mask,
)
from scripts.multitimeframe_features_v3 import feature_names


@pytest.mark.parametrize("family", ["daily", "weekly", "monthly"])
def test_ablation_partition_is_complete_and_disjoint(family: str) -> None:
    baseline = set(feature_mask(family, "baseline"))
    regime = set(feature_mask(family, "regime_only_delta"))
    all_features = set(feature_mask(family, "all_features"))
    assert baseline
    assert regime
    assert baseline.isdisjoint(regime)
    assert baseline | regime == all_features
    assert len(all_features) == len(feature_names(family))


@pytest.mark.parametrize("family", ["daily", "weekly", "monthly"])
def test_manifest_is_fail_closed_for_locked_evidence(family: str) -> None:
    manifest = ablation_manifest(family)
    assert manifest["scope"] == "development_validation_only"
    assert manifest["fresh_locked_oos_access"] is False
    assert manifest["v2_locked_oos_used_for_tuning"] is False
    assert tuple(manifest["ablations"]) == ABLATIONS


def test_apply_mask_preserves_declared_order() -> None:
    assert apply_mask([10.0, 20.0, 30.0, 40.0], (3, 1)) == [40.0, 20.0]


def test_unknown_ablation_fails_closed() -> None:
    with pytest.raises(ValueError):
        feature_mask("daily", "anything_else")
