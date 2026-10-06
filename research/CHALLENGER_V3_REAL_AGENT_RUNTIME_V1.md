# Challenger V3 Real Research Agent Runtime — Protocol v1

Status: DEVELOPMENT / VALIDATION ONLY

## Purpose
Introduce genuinely intelligent research agents without allowing agents to become the statistical judge, alter confirmatory rules, or access protected evidence.

## Research council
1. Feature Research Agent — proposes causal point-in-time features and isolated ablations.
2. Statistical Methods Agent — challenges inference, dependence assumptions, multiplicity, and sample adequacy.
3. Leakage & Provenance Agent — searches for future information, target leakage, timestamp/provenance failures, and split contamination.
4. Neural Time-Series Agent — proposes bounded neural challengers with train-fold-only normalization and deterministic evaluation.
5. Devil's Advocate Agent — attempts to falsify promising results and identifies alternative explanations.
6. Orchestrator — routes tasks, checks required evidence envelopes, records disagreements, and may recommend the next development experiment. It cannot authorize Freeze or promotion.

## Hard isolation boundary
Agents MAY read:
- development/validation evidence;
- source code, tests, manifests, feature definitions, model configs;
- corrected development statistical diagnostics;
- public research needed to formulate hypotheses.

Agents MUST NOT read or use:
- future Challenger V3 Fresh Locked OOS outcomes;
- V2 locked-OOS outcomes for tuning;
- prospective holdout outcomes before their declared evaluation;
- production trading decisions or credentials.

If protected evidence is present in a supplied context, the task fails closed.

## Required evidence envelope
Every agent response must be machine-recordable and contain:
- agent_id, agent_version, role, task_id;
- created_at_utc, code_commit, protocol_version;
- scope = development_validation_only;
- hypothesis and causal rationale;
- exact input artifact/dataset identities;
- proposed method;
- point_in_time_rule;
- implementation_and_test_plan;
- evidence and counterevidence;
- leakage_checks;
- failure_modes;
- reproducibility;
- confidence;
- recommendation in {continue, reject, audit};
- fresh_locked_oos_access = false;
- v2_locked_oos_used_for_tuning = false;
- freeze_authorized = false;
- production_eligible = false.

Missing required fields => reject the response.

## Deterministic gate
An agent proposal is not evidence. The only admissible path is:

agent hypothesis
→ deterministic implementation
→ unit/property/adversarial tests
→ development tournament
→ nested selection
→ corrected statistical judge
→ leakage/adversarial review

No agent vote, confidence score, or provider output may crown a Champion.

## Parallel execution policy
Independent tasks may run in parallel. Tasks that depend on evidence must declare dependencies. Parallel agents must not share hidden conclusions before producing their own first-pass report; the Orchestrator may reconcile reports afterward.

Initial bounded parallel wave:
- FEATURE-01: explain and improve the 1w trend/regime signal without coefficient transfer.
- STATS-01: audit corrected Judge outputs and sample-adequacy failures.
- LEAKAGE-01: adversarially audit feature timestamps, labels, nested boundaries, and target maturity.
- NEURAL-01: specify one bounded neural challenger; no broad architecture search.
- DEVIL-01: try to falsify the strongest development signal and identify concentration/regime dependence.

## Model/provider policy
Provider independence is required. Provider/model names are runtime configuration, not scientific identity. A provider-connected agent gets read-only research context by default and no GitHub write, workflow-dispatch, secret, trading, or protected-data permission.

## Cost and stopping
Start with the five independent research agents above. Do not scale agent count merely for parallelism. Add an agent only for a genuinely distinct hypothesis or audit lane. Stop a lane when evidence rejects it or marginal information gain is low.

## Freeze boundary
Real research agents operate before Freeze. Once a V3 candidate/protocol is frozen, agents may audit the frozen package but may not adapt it using Fresh Locked OOS outcomes.

## Audit trail
Persist prompt/version, model/provider configuration, input identities, structured response, validation result, implementation commit/PR, CI run, and resulting development evidence. Preserve rejected hypotheses as evidence against repeated research fishing.
