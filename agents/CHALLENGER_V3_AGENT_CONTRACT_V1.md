# Challenger V3 Agent Contract v1

Status: ACTIVE — DEVELOPMENT/VALIDATION ONLY
Applies to: research/challenger-v3-agents

Every V3 research agent must emit a versioned, machine-auditable evidence package. An agent is a bounded research worker, not an authority and not a production trader.

## Required envelope
Each output must contain:
- agent_id and agent_version
- role
- task_id
- created_at_utc
- input_artifact_ids / dataset identities
- code_commit
- protocol_version
- development_or_validation_scope
- hypothesis
- method
- result
- evidence
- counterevidence
- missing_data
- leakage_checks
- reproducibility
- confidence (calibrated when applicable)
- recommendation: continue | reject | audit
- production_eligible: false

## Role permissions
- Orchestrator: assign/merge/route; cannot alter evidence or promote.
- Data/Provenance: read/validate data and manifests; cannot choose a model from performance.
- Feature Research: propose point-in-time features using development data only; no fresh OOS.
- Classical Modeling: train/evaluate declared classical candidates in development/validation.
- Neural Time-Series: train/evaluate sequence candidates only through leakage-safe adapters.
- Statistics: define/execute declared comparisons; cannot tune candidates after confirmatory outcomes.
- Leakage/Audit: adversarial read access; may veto progression on leakage/reproducibility defects.
- Devil's Advocate: search for alternative explanations/selection bias; cannot rewrite results.

## Mandatory isolation
V2 locked-OOS results are historical evidence and are prohibited as a V3 optimization target. V3 candidate, feature, hyperparameter, selection, and stopping decisions must not be optimized against those outcomes.

## Orchestration rule
Parallelize only independent tasks. Each spawned task needs a distinct hypothesis or audit responsibility, explicit inputs, measurable output, and stop condition. More agents are not evidence of better research.

## Promotion rule
No agent vote can crown a Champion. Promotion requires the predeclared V3 pipeline: development -> validation -> freeze -> new fresh OOS -> statistical gate -> independent replication -> prospective confirmation -> registry/manual authorization.
