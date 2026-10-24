"""Bounded design triage tests; no actual model or provider is invoked."""

import copy
import json
import unittest
from pathlib import Path

from scripts.alpha_discovery_engine import evaluate

MANIFEST = (
    Path(__file__).resolve().parents[1] / "research" / "alpha_discovery_pilot_20261024.json"
)


class AlphaDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.packet = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def review(self, role, finding="CLEAR", author=None):
        return {
            "hypothesis_id": "regime_conditioned_signal",
            "role": role,
            "reviewer_id": author or f"reviewer_{role}",
            "finding": finding,
            "rationale": "No real data have been inspected by this synthetic reviewer fixture.",
        }

    def test_unreviewed_hypothesis_has_no_scientific_authorization(self):
        result = evaluate(self.packet)
        row = result["hypotheses"][0]
        self.assertEqual(row["status"], "CHALLENGE_PENDING")
        self.assertEqual(row["missing_roles"], ["mechanism", "adversary", "statistics"])
        self.assertIsNone(result["selected_winner"])
        self.assertEqual(result["scientific_authorization"], "NO_RUN")
        self.assertEqual(result["real_agents_dispatched"], 0)
        self.assertEqual(result["external_cost_usd"], 0)

    def test_three_claimed_clear_reviews_still_do_not_authorize_run(self):
        self.packet["reviews"] = [self.review(role) for role in ("mechanism", "adversary", "statistics")]
        result = evaluate(self.packet)
        self.assertEqual(result["hypotheses"][0]["status"], "DESIGN_REVIEWED_ONLY")
        self.assertEqual(
            result["hypotheses"][0]["next_action"], "EXTERNAL_CUSTODY_AND_PREREGISTRATION"
        )
        self.assertFalse(result["source_vintage_verified"])
        self.assertEqual(result["scientific_authorization"], "NO_RUN")

    def test_adversarial_veto_rejects_despite_other_approvals(self):
        self.packet["reviews"] = [
            self.review("mechanism"),
            self.review("adversary", "VETO"),
            self.review("statistics"),
        ]
        row = evaluate(self.packet)["hypotheses"][0]
        self.assertEqual(row["status"], "REJECT")
        self.assertEqual(row["veto_roles"], ["adversary"])

    def test_revision_blocks_design_reviewed_state(self):
        self.packet["reviews"] = [
            self.review("mechanism"),
            self.review("adversary", "REVISE"),
            self.review("statistics"),
        ]
        self.assertEqual(evaluate(self.packet)["hypotheses"][0]["status"], "REVISE")

    def test_duplicate_reviewer_identity_is_not_independent(self):
        self.packet["reviews"] = [
            self.review("mechanism", author="one_author"),
            self.review("adversary", author="one_author"),
        ]
        with self.assertRaisesRegex(ValueError, "distinct"):
            evaluate(self.packet)

    def test_outcome_smuggling_is_rejected(self):
        self.packet["hypotheses"][0]["observed_win_rate"] = 0.98
        with self.assertRaisesRegex(ValueError, "fields"):
            evaluate(self.packet)

    def test_existing_scores_cannot_be_described_as_untouched(self):
        self.packet["hypotheses"][0]["historical_outcome_exposure"] = "UNTOUCHED"
        with self.assertRaisesRegex(ValueError, "prior outcome"):
            evaluate(self.packet)

    def test_no_budget_or_live_mode_creep(self):
        self.packet["max_external_cost_usd"] = 10
        with self.assertRaisesRegex(ValueError, "cost"):
            evaluate(self.packet)
        self.packet["max_external_cost_usd"] = 0
        self.packet["mode"] = "live"
        with self.assertRaisesRegex(ValueError, "design_only"):
            evaluate(self.packet)

    def test_reused_mechanism_is_not_distinct_hypothesis(self):
        dup = copy.deepcopy(self.packet["hypotheses"][0])
        dup["id"] = "second_hypothesis"
        self.packet["hypotheses"].append(dup)
        with self.assertRaisesRegex(ValueError, "Duplicate mechanisms"):
            evaluate(self.packet)

    def test_no_chosen_horizon_or_unapproved_baseline(self):
        self.packet["hypotheses"][0]["horizon"] = "12h"
        with self.assertRaisesRegex(ValueError, "preregistration"):
            evaluate(self.packet)
        self.packet["hypotheses"][0]["horizon"] = "UNDECIDED"
        self.packet["hypotheses"][0]["baseline"] = "ALWAYS_UP"
        with self.assertRaisesRegex(ValueError, "persistence"):
            evaluate(self.packet)


if __name__ == "__main__":
    unittest.main()
