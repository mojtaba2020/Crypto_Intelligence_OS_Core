# Challenger V2 Freeze Record

Status: FROZEN BEFORE LOCKED OOS
Date: 2026-09-30
Branch: research/challenger-v2
Development/validation source commit: 266120afc6f727e0226fe7386fe4520dd8e75bb1
Source workflow: BTC Multi-Timeframe Real Data Audit, run 36765285405
Protocol: research/CHALLENGER_V2_PROTOCOL.md

Selection rule: minimum validation MAPE with the predeclared candidate-order tie break.

Frozen selections:
- 1d: boosting
- 2d: boosting
- 3d: boosting
- 1w: extra_trees
- 2w: ridge
- 3w: ridge

1mo and 3mo are excluded from this confirmatory round because the predeclared history requirement was not met. The threshold must not be lowered after seeing this result.

At freeze time:
- locked OOS consumed: false
- production promotion: false
- Persistence remains Champion.

Invariants:
1. No candidate, hyperparameter, feature, split, or selection-rule change after this freeze may use this version's locked OOS.
2. Locked OOS is single-use confirmatory evidence.
3. Failure on locked OOS is retained as evidence and must not be tuned away.
4. Promotion requires the predeclared statistical gate and independent-exchange replication before prospective confirmation and registry eligibility.

Next gate: Fresh Locked OOS, using paired losses, dependence-aware uncertainty, and multiplicity control.
