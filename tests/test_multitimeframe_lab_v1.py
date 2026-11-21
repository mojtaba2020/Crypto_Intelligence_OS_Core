from __future__ import annotations

from scripts.multitimeframe_lab_v1 import SPECS, manifest, validate_contract


def test_all_requested_horizons_are_locked_in_contract() -> None:
    required = {
        "1h",
        "2h",
        "3h",
        "4h",
        "12h",
        "1d",
        "2d",
        "3d",
        "1w",
        "2w",
        "3w",
        "1mo",
        "3mo",
        "6mo",
        "1y",
        "2y",
        "3y",
        "4y",
        "5y",
        "6y",
        "7y",
        "8y",
    }
    assert {spec.label for spec in SPECS} == required


def test_macro_cycle_horizons_cannot_promote() -> None:
    macro = [spec for spec in SPECS if spec.family == "macro_cycle"]
    assert macro
    assert all(not spec.promotion_eligible for spec in macro)


def test_contract_is_fail_closed_and_requires_replication() -> None:
    report = manifest()
    policy = report["statistical_policy"]
    assert isinstance(policy, dict)
    assert policy["automatic_promotion"] is False
    assert policy["independent_exchange_replication_required"] is True
    assert policy["prospective_confirmation_required"] is True
    assert report["locked_test_reuse"] == "forbidden_for_feature_or_hyperparameter_selection"


def test_contract_validation_passes() -> None:
    validate_contract()
