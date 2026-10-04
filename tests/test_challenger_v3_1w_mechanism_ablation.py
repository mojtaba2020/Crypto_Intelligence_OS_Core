from challenger_v3_1w_mechanism_ablation import CONFIGS, SUBSETS, _subset_indices
from multitimeframe_features_v3 import feature_names

def test_mechanism_grid_is_bounded_and_predeclared():
    assert SUBSETS == ("regime_7","stable_6")
    assert [x[1] for x in CONFIGS] == [None,0.0,0.25,0.50,0.75,1.0]

def test_stable_six_only_removes_range_position():
    names=feature_names("weekly")
    seven=[names[i] for i in _subset_indices("regime_7")]
    six=[names[i] for i in _subset_indices("stable_6")]
    assert len(seven)==7 and len(six)==6
    assert "range_position_13" in seven and "range_position_13" not in six
    assert set(six)==set(seven)-{"range_position_13"}
