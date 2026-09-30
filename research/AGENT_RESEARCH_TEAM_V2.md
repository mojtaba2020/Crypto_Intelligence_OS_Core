# Agent Research Team V2

Agents are research workers, not judges. They must not use Evidence V1 locked outcomes to tune
features, models, hyperparameters, or research priorities.

## Lanes

- data_quality: source integrity, gaps, provenance, canonical time.
- feature_research: point-in-time features and ablations on development/validation only.
- classical_ml: linear, tree and boosting challengers.
- neural_ts: compact sequence challengers after leakage-safe tests.
- foundation_ts: transformer/foundation baselines with verified license/dependency metadata.
- macro_cycle: halving/cycle/drawdown hypotheses; descriptive only for sparse horizons.
- reproducibility_audit: manifests, hashes, deterministic configs and leakage checks.

## Authority boundary

Agents may propose and build challengers. They cannot select a Champion, inspect a fresh locked
evaluation for tuning, authorize production, or waive statistical/replication/prospective gates.

All confirmatory decisions remain deterministic code in the central Judge.
