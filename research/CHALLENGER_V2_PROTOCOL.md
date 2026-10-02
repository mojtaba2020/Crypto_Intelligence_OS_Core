# Challenger V2 Research Protocol

## Purpose

Search for genuine predictive edge across Crypto Intelligence OS horizons without reusing
Evidence V1 locked outcomes for model or hyperparameter selection.

## Frozen starting point

- Parent evidence commit: `76401f3f5f495d30ce2aa120ccc7b1892e41c31f`
- Evidence V1 artifact: `btc-real-multitimeframe-evidence-v1`
- Artifact SHA-256: `72b14a656a798acf20abf8f4af5306a91ba466282878314548c27e27a0f711ad`
- Evidence V1 status: no statistically confirmed challenger promotion.
- Persistence remains Champion.

## Horizon map

1h, 2h, 3h, 4h, 12h,
1d, 2d, 3d,
1w, 2w, 3w,
1mo, 3mo,
6mo, 1y, 2y, 3y, 4y, 5y, 6y, 7y, 8y.

The 6mo-8y macro-cycle family remains descriptive/hypothesis-generating until the
available independent-cycle count supports confirmatory inference.

## Research lanes

1. Data & provenance: immutable source identity, completeness metadata, as-of cutoff,
   instrument/exchange/range provenance.
2. Feature research: point-in-time features only; no locked Evidence V1 outcome may guide
   feature acceptance.
3. Classical ML: strong tree/boosting/linear challengers.
4. Neural time series: sequence models only after leakage-safe adapters/tests exist.
5. Transformer/foundation models: optional research adapters; licenses and dependencies
   must be verified before production eligibility.
6. Macro/cycle: halving/cycle/drawdown/range hypotheses with sparse-sample safeguards.
7. Statistics: paired losses, dependence-aware uncertainty, multiplicity control.
8. Audit: reproducibility, temporal leakage, data-gap and provenance checks.

## Promotion path

Development -> Validation -> Freeze -> Fresh OOS -> multiplicity-adjusted statistical gate
-> independent exchange replication -> prospective confirmation -> registry eligibility
-> manual live authorization.

No agent, model family, workflow success, or raw metric may bypass this path.

## Immediate engineering gates

Before a new confirmatory evaluation:

- fingerprint full prepared records including completeness metadata;
- propagate explicit as-of timestamps;
- record source ID, instrument, requested range and native-data overlap;
- expose origin-level paired losses for reproducible statistical/regime audits;
- predeclare deterministic candidate tie-break behavior;
- prove canonical-grid split semantics with regression tests;
- investigate monthly-history insufficiency without lowering thresholds to fit an outcome.

Evidence V1 is now read-only evidence. Challenger V2 development must not tune against its
locked outcomes.


## Classical lane V2 freeze

Before any fresh locked-OOS evaluation, the classical development lane is frozen to the
following deterministic candidate order and configurations. The order is also the
validation tie-break order; it is not a performance ranking.

1. ridge: frozen V1 ridge implementation, alpha=1.0.
2. elastic_net: StandardScaler + ElasticNet(alpha=0.0001, l1_ratio=0.25,
   max_iter=5000, random_state=20260929).
3. extra_trees: frozen V1 ExtraTreesRegressor(n_estimators=200,
   min_samples_leaf=5, random_state=20260929, n_jobs=-1).
4. random_forest: RandomForestRegressor(n_estimators=200, min_samples_leaf=5,
   max_features=0.75, random_state=20260929, n_jobs=-1).
5. hist_gradient_boosting: HistGradientBoostingRegressor(learning_rate=0.05,
   max_iter=150, max_leaf_nodes=15, l2_regularization=1.0,
   random_state=20260929).
6. boosting: frozen V1 GradientBoostingRegressor(n_estimators=100,
   learning_rate=0.05, max_depth=2, random_state=20260929).

These are deliberately compact representatives of regularized linear, bagged-tree, and
boosted-tree families. No hyperparameter search against Evidence V1 locked outcomes is
permitted. Any future configuration change creates a new protocol version and must occur
before that version sees fresh locked OOS.

V2 development and validation may compare these candidates. Fresh locked OOS remains
single-use and must not be consumed until candidate selection, feature definitions,
split rules, statistical family, and provenance fingerprint are frozen.
