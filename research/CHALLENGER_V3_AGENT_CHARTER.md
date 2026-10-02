# Challenger V3 Agent Research Charter

Status: DEVELOPMENT / VALIDATION ONLY
Parent: Challenger V2 locked-OOS evidence is immutable and MUST NOT be used for V3 tuning.
Branch: research/challenger-v3-agents

## Objective
Develop genuinely new BTC forecasting challengers under leakage-safe, evidence-first research. Persistence remains Champion until a future V3 confirmatory protocol passes every gate.

## Initial agent team
1. Data & Provenance Agent — dataset identity, as-of cutoffs, gaps, source overlap, reproducibility.
2. Feature Research Agent — proposes point-in-time features using development data only.
3. Classical Modeling Agent — regularized/tree/boosting candidates; no locked-OOS access.
4. Neural Time-Series Agent — sequence candidates only after leakage-safe adapters/tests exist.
5. Statistics Agent — paired losses, dependence-aware uncertainty, calibration, multiplicity plan.
6. Leakage & Audit Agent — adversarial temporal-leakage and reproducibility review.
7. Devil's Advocate Agent — attempts to invalidate claimed improvements and detect selection bias.
8. Orchestrator — assigns bounded tasks and merges evidence; cannot promote a model.

Agent count scales only when independent work justifies it. Do not spawn agents merely to increase count.

## Hard boundaries
- Challenger V2 locked OOS is read-only historical evidence. Never optimize V3 against it.
- No agent may alter evidence, promotion criteria, or a frozen protocol after seeing confirmatory outcomes.
- Development and validation must remain physically/logically separated from future fresh OOS.
- Deterministic calculations stay in code; agents propose/review hypotheses and evidence.
- Every agent output must identify inputs, versions, evidence, counterarguments, missing data, and reproducibility information.
- No automatic production promotion or trading action.

## V3 sequence
Research lanes -> reproducible candidate implementations -> tests -> development tournament -> validation -> deterministic selection -> V3 freeze -> NEW fresh OOS -> statistical gate -> independent exchange replication -> prospective confirmation -> registry eligibility -> manual live authorization.

## Entry criteria for V3 freeze
- data/provenance manifest complete;
- feature definitions versioned and point-in-time;
- candidate configs and deterministic tie-break frozen;
- split semantics regression-tested;
- origin-level paired losses reproducible;
- statistical family, alpha, uncertainty method, multiplicity correction and minimum sample rules predeclared;
- future fresh-OOS dataset/cutoff identified without inspecting outcomes;
- leakage/audit and Devil's Advocate reviews passed.

## Current decision
Begin with the eight bounded roles above. Additional agents are admitted only when they have a distinct hypothesis or audit responsibility and a measurable output.
