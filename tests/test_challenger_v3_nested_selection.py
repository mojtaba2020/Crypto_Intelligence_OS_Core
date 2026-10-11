import pytest
from scripts.challenger_v3_nested_selection import (
    NestedSelectionPolicy,
    evidence_manifest,
    heldout_paired_differences,
    purged_diagnostic_records,
    select_candidate,
)


def _records(n=50):
    rows = []
    for i in range(n):
        rows.append(
            {
                "persistence_error": 0.10,
                "candidate_errors": {
                    "a": 0.05 if i < 30 else 0.12,
                    "b": 0.06 if i < 30 else 0.07,
                },
            }
        )
    return rows


def test_selection_uses_earlier_origins_only():
    winner, cut = select_candidate(_records(), ("a", "b"))
    assert cut == 30
    assert winner == "a"


def test_diagnostic_subset_is_not_used_for_selection():
    rows = _records()
    winner, cut = select_candidate(rows, ("a", "b"))
    diffs = heldout_paired_differences(rows, winner, cut)
    assert winner == "a"
    assert len(diffs) == 20
    assert all(x < 0 for x in diffs)


def test_tie_break_is_canonical_and_order_invariant():
    rows = _records()
    for row in rows:
        row["candidate_errors"]["a"] = 0.05
        row["candidate_errors"]["b"] = 0.05
    first, first_cut = select_candidate(rows, ("b", "a"))
    second, second_cut = select_candidate(rows, ("a", "b"))
    assert first == second == "a"
    assert first_cut == second_cut == 30


def test_duplicate_candidate_names_fail_closed():
    with pytest.raises(ValueError, match="unique"):
        select_candidate(_records(), ("a", "a"))


def test_policy_fails_closed_when_too_few_origins():
    try:
        NestedSelectionPolicy().boundary(34)
    except ValueError:
        pass
    else:
        raise AssertionError("expected fail-closed boundary")


def test_manifest_preserves_locked_evidence_boundaries():
    m = evidence_manifest("a", 30, 50)
    assert m["fresh_locked_oos_access"] is False
    assert m["v2_locked_oos_used_for_tuning"] is False
    assert m["confirmatory"] is False
    assert m["production_eligible"] is False


def test_target_maturity_purge_only_removes_overlapping_origins():
    rows = _records()
    daily, daily_purged = purged_diagnostic_records(
        rows, 30, horizon_bars=2, evaluation_step_bars=30
    )
    monthly, monthly_purged = purged_diagnostic_records(
        rows, 30, horizon_bars=3, evaluation_step_bars=1
    )
    assert daily_purged == 0
    assert len(daily) == 20
    assert monthly_purged == 2
    assert len(monthly) == 18


def test_exact_timestamp_purge_handles_irregular_calendar_spacing():
    rows = _records(8)
    origin_timestamps = [0, 31, 59, 90, 120, 151, 181, 212]
    for row, timestamp in zip(rows, origin_timestamps, strict=True):
        row["origin_timestamp"] = timestamp
    rows[2]["target_timestamp"] = 120
    diagnostic, purged = purged_diagnostic_records(rows, 3, horizon_bars=3, evaluation_step_bars=1)
    assert purged == 1
    assert diagnostic[0]["origin_timestamp"] == 120


def test_exact_timestamp_purge_rejects_partial_metadata():
    rows = _records()
    for i, row in enumerate(rows):
        row["origin_timestamp"] = i
    rows[29]["target_timestamp"] = 32
    rows[31].pop("origin_timestamp")
    with pytest.raises(ValueError, match="complete timestamp metadata"):
        purged_diagnostic_records(rows, 30, horizon_bars=3, evaluation_step_bars=1)


def test_target_maturity_purge_fails_if_no_diagnostics_remain():
    with pytest.raises(ValueError, match="leaves no diagnostic"):
        purged_diagnostic_records(_records(35), 20, horizon_bars=30, evaluation_step_bars=1)
