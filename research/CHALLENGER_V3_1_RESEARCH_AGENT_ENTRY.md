# Challenger V3.1 Research Agent Entry Protocol

Status: DEVELOPMENT / VALIDATION ONLY

## Purpose

V3.1 is the first controlled entry of intelligent research agents into the
Crypto Intelligence OS laboratory. Agents generate hypotheses and review
evidence; deterministic code remains responsible for calculations, dataset
identity, losses, statistical tests, and promotion gates.

## Initial research council

1. Feature Research Agent — proposes genuinely new point-in-time information.
2. Neural Research Agent — proposes bounded sequence-model experiments.
3. Statistics Agent — audits selection bias, uncertainty, multiplicity and power.
4. Leakage/Audit Agent — attempts to falsify provenance and temporal isolation.
5. Devil's Advocate — searches for simpler explanations, instability and overfit.
6. Orchestrator — schedules independent tasks and reconciles disagreements.

Data/Provenance remains a deterministic gate and Classical Modeling remains an
existing benchmark lane.

## Permissions

Agents MAY read development/validation manifests, feature definitions, candidate
configs, nested diagnostic summaries, and source code needed for their task.

Agents MUST NOT read or request future V3 Fresh Locked OOS outcomes, use V2
Locked OOS for tuning, change statistical thresholds after seeing results,
authorize Freeze, declare a Champion, promote production, or execute trades.

## Required evidence envelope

Every research proposal must contain:
- hypothesis and causal/time-series rationale;
- exact information set and as-of availability rule;
- implementation sketch and deterministic test plan;
- expected failure modes and counterevidence;
- ablation that can isolate incremental information;
- leakage checks;
- complexity/overfit risk;
- reproducibility metadata;
- recommendation: test / reject / audit.

An agent opinion is never evidence of predictive edge.

## V3.1 feature research queue

Priority A (implement first, independently ablated):
- robust trailing volume state (median/MAD or equivalent causal normalization);
- volume momentum/change at predeclared scales;
- trailing volatility percentile/rank using only historical reference values;
- deterministic trend × volatility regime interactions;
- regime transition/state-change indicators.

Priority B (separate high-overfit-risk lane):
- halving/cycle features known at forecast origin.

External/on-chain/macro/order-book inputs are prohibited until each source has
timestamped as-of provenance and a point-in-time availability audit.

## Neural lane

Neural experiments begin only as bounded challengers. Initial implementations
must use train-fold-only normalization, walk-forward validation, deterministic
seeds, reported parameter counts, early stopping without diagnostic/fresh-OOS
access, and the same target/loss accounting as classical challengers.

Model families are not promoted because they are newer or more complex.

## Decision sequence

Agent proposal -> deterministic implementation -> unit/leakage tests -> isolated
ablation -> nested selection -> held-out development diagnostic -> Statistical
Judge -> adversarial audit.

Only accumulated Development/Validation evidence can justify preparation for a
future Freeze. Fresh Locked OOS remains unopened until the Freeze record is
complete.
