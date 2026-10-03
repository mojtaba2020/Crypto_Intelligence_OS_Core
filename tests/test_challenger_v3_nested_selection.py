from scripts.challenger_v3_nested_selection import (
    NestedSelectionPolicy,
    evidence_manifest,
    heldout_paired_differences,
    select_candidate,
)


def _records(n=50):
    rows = []
    for i in range(n):
        rows.append({
            "persistence_error": 0.10,
            "candidate_errors": {
                "a": 0.05 if i < 30 else 0.12,
                "b": 0.06 if i < 30 else 0.07,
            },
        })
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
