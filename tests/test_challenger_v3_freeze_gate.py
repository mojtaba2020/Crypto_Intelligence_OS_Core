from scripts.challenger_v3_freeze_gate import evaluate_report, evaluate_row


def _row():
    return {
        "horizon": "1w",
        "ablation": "regime_only_delta",
        "candidate": "elastic_net",
        "inference_eligible": True,
        "diagnostic_pass": True,
        "mean_paired_improvement": 0.01,
        "one_sided_lower_confidence_bound_95": 0.001,
        "holm_reject": True,
        "sensitivity_diagnostics": {
            "stationary_bootstrap": {"selection_rule": "never_replaces_primary_method"},
            "hac": {"selection_rule": "never_replaces_primary_method"},
            "contiguous_origin_deletion": {
                "positive_after_every_tested_deletion": True,
            },
            "chronological_regimes": {"all_thirds_positive": True},
            "positive_concentration": {"remains_positive_after_top_k_removal": True},
        },
    }


def _report(row=None):
    return {
        "fresh_locked_oos_access": False,
        "v2_locked_oos_used_for_tuning": False,
        "production_promotion": False,
        "results": [_row() if row is None else row],
    }


def test_strong_development_candidate_is_only_freeze_ready_not_authorized():
    output = evaluate_report(_report())
    assert output["freeze_ready_candidate_count"] == 1
    assert output["results"][0]["freeze_ready"] is True
    assert output["freeze_authorized"] is False
    assert output["fresh_oos_authorized"] is False
    assert output["champion_authorized"] is False
    assert output["production_eligible"] is False
    assert output["manual_freeze_decision_required"] is True


def test_any_adversarial_failure_blocks_freeze_readiness():
    row = _row()
    row["sensitivity_diagnostics"]["chronological_regimes"]["all_thirds_positive"] = False
    result = evaluate_row(row)
    assert result["freeze_ready"] is False
    assert result["checks"]["all_chronological_thirds_positive"] is False


def test_missing_sensitivity_packet_fails_closed():
    row = _row()
    del row["sensitivity_diagnostics"]["positive_concentration"]
    result = evaluate_row(row)
    assert result["freeze_ready"] is False
    assert result["checks"]["sensitivity_packet_complete"] is False


def test_locked_oos_contact_is_rejected_before_freeze():
    report = _report()
    report["fresh_locked_oos_access"] = True
    try:
        evaluate_report(report)
    except ValueError as exc:
        assert "Fresh Locked OOS" in str(exc)
    else:
        raise AssertionError("expected locked-OOS fail-closed guard")


def test_v2_locked_tuning_is_rejected_before_freeze():
    report = _report()
    report["v2_locked_oos_used_for_tuning"] = True
    try:
        evaluate_report(report)
    except ValueError as exc:
        assert "V2 locked OOS" in str(exc)
    else:
        raise AssertionError("expected V2 locked-OOS fail-closed guard")
