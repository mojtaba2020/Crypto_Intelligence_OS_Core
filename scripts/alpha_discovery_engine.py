"""Falsification-first alpha hypothesis triage; no models, data, or agents are run.

Use only with price/outcome-free research design packets. Agent opinions do not
constitute independent evidence, external custody, or scientific authorization.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROLES = ("mechanism", "adversary", "statistics")
FINDINGS = {"CLEAR", "REVISE", "VETO"}
ID = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
HYPOTHESIS_FIELDS = {
    "id",
    "mechanism",
    "pre_origin_features",
    "falsification_rule",
    "negative_control",
    "baseline",
    "primary_metric",
    "horizon",
    "historical_outcome_exposure",
}
REVIEW_FIELDS = {"hypothesis_id", "role", "reviewer_id", "finding", "rationale"}
PLAN_FIELDS = {"schema_version", "mode", "max_external_cost_usd", "hypotheses", "reviews"}
BANNED_TEXT = ("future_return", "future_price", "observed_pvalue", "observed_win_rate")


def _required_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 1500:
        raise ValueError(f"{name} must be a nonempty bounded string")
    if any(token in value.lower() for token in BANNED_TEXT):
        raise ValueError(f"{name} contains a prohibited outcome claim")
    return value


def evaluate(packet: dict[str, Any]) -> dict[str, Any]:
    """Plan a small critique tournament without consuming price outcomes."""
    if not isinstance(packet, dict) or set(packet) != PLAN_FIELDS:
        raise ValueError("Unexpected or missing plan fields")
    if packet["schema_version"] != 1 or packet["mode"] != "design_only":
        raise ValueError("Only schema 1 design_only is supported")
    if type(packet["max_external_cost_usd"]) is not int or packet["max_external_cost_usd"] != 0:
        raise ValueError("Pilot external cost must be exactly zero")
    hypotheses = packet["hypotheses"]
    reviews = packet["reviews"]
    if not isinstance(hypotheses, list) or not 1 <= len(hypotheses) <= 2:
        raise ValueError("Pilot must contain one or two hypotheses")
    if not isinstance(reviews, list) or len(reviews) > len(hypotheses) * len(ROLES):
        raise ValueError("Too many reviews")
    ids: set[str] = set()
    seen_mechanisms: set[str] = set()
    for h in hypotheses:
        if not isinstance(h, dict) or set(h) != HYPOTHESIS_FIELDS:
            raise ValueError("Unexpected or missing hypothesis fields")
        ident = h["id"]
        if not isinstance(ident, str) or not ID.fullmatch(ident) or ident in ids:
            raise ValueError("Hypothesis IDs must be safe and unique")
        ids.add(ident)
        for field in HYPOTHESIS_FIELDS - {"id"}:
            _required_string(h[field], field)
        mechanism = h["mechanism"].strip().casefold()
        if mechanism in seen_mechanisms:
            raise ValueError("Duplicate mechanisms are not independent discoveries")
        seen_mechanisms.add(mechanism)
        if h["historical_outcome_exposure"] != "ALREADY_EXPOSED":
            raise ValueError("This design phase must admit prior outcome exposure")
        if h["horizon"] != "UNDECIDED":
            raise ValueError("Horizon requires separate prospective preregistration")
        if h["baseline"] != "PERSISTENCE":
            raise ValueError("Pilot baseline must be persistence")
        if h["primary_metric"] != "PAIRED_ABSOLUTE_LOG_PRICE_ERROR":
            raise ValueError("Only a fixed candidate primary metric is supported")

    indexed: dict[str, dict[str, dict[str, Any]]] = {ident: {} for ident in ids}
    authors: dict[str, set[str]] = {ident: set() for ident in ids}
    for review in reviews:
        if not isinstance(review, dict) or set(review) != REVIEW_FIELDS:
            raise ValueError("Unexpected or missing review fields")
        ident, role = review["hypothesis_id"], review["role"]
        if ident not in ids or role not in ROLES or role in indexed[ident]:
            raise ValueError("Unknown hypothesis/role or duplicate role review")
        author = _required_string(review["reviewer_id"], "reviewer_id")
        if not ID.fullmatch(author) or author in authors[ident]:
            raise ValueError("Reviewer identities must be distinct within a hypothesis")
        authors[ident].add(author)
        if review["finding"] not in FINDINGS:
            raise ValueError("Invalid finding")
        _required_string(review["rationale"], "rationale")
        indexed[ident][role] = review

    dispositions = []
    for h in hypotheses:
        by_role = indexed[h["id"]]
        missing = [role for role in ROLES if role not in by_role]
        vetoes = [role for role in ROLES if by_role.get(role, {}).get("finding") == "VETO"]
        revisions = [role for role in ROLES if by_role.get(role, {}).get("finding") == "REVISE"]
        if vetoes:
            status, next_action = "REJECT", "DO_NOT_ADVANCE_THIS_HYPOTHESIS"
        elif revisions:
            status, next_action = "REVISE", "REWRITE_BEFORE_ANOTHER_BLIND_CRITIQUE"
        elif missing:
            status, next_action = "CHALLENGE_PENDING", "OBTAIN_MISSING_ROLE_REVIEWS"
        else:
            status, next_action = "DESIGN_REVIEWED_ONLY", "EXTERNAL_CUSTODY_AND_PREREGISTRATION"
        dispositions.append(
            {
                "id": h["id"],
                "status": status,
                "next_action": next_action,
                "missing_roles": missing,
                "veto_roles": vetoes,
                "revision_roles": revisions,
                "mechanism": h["mechanism"],
                "falsification_rule": h["falsification_rule"],
                "negative_control": h["negative_control"],
                "review_independence": "SELF_REPORTED_IDENTITIES_ONLY",
            }
        )
    return {
        "mode": "design_only",
        "experiment_type": "FALSIFICATION_FIRST_ALPHA_DISCOVERY",
        "hypotheses": dispositions,
        "selected_winner": None,
        "real_agents_dispatched": 0,
        "external_calls": 0,
        "external_cost_usd": 0,
        "source_vintage_verified": False,
        "independent_publication_verified": False,
        "pilot_preregistered": False,
        "scientific_authorization": "NO_RUN",
        "stage7_freeze_authorized": False,
        "note": "Reviewer labels are claims, not verified independent signatures.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()
    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    print(json.dumps(evaluate(data), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
