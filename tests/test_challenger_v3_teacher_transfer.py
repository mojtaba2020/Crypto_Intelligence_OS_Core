from challenger_v3_teacher_transfer import (
    RECIPIENTS,
    STABLE_FEATURES,
    stable_feature_indices,
)
from multitimeframe_features_v3 import feature_names


def test_teacher_subset_is_exact_and_weekly_native():
    names = feature_names("weekly")
    selected = [names[i] for i in stable_feature_indices()]
    assert tuple(selected) == STABLE_FEATURES
    assert "range_position_13" not in selected


def test_teacher_is_not_a_recipient():
    assert "elastic_net" not in RECIPIENTS


def test_transfer_subset_is_small_and_nonempty():
    assert len(stable_feature_indices()) == 6
    assert len(set(stable_feature_indices())) == 6
