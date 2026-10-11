# Challenger V3 pre-freeze family correction

Status: DEVELOPMENT / VALIDATION ONLY
Decision: the earlier 1w-only pre-freeze run is advisory and cannot establish family-wide statistical readiness.

## Reason
The statistical judge predeclares a Holm-Bonferroni family across all evaluated
horizon x ablation winners. Running only 1w evaluates four hypotheses and is not
the intended declared family used for a freeze decision.

## Correction
The pre-freeze workflow now evaluates the declared six-horizon curriculum:
1d, 2d, 3d, 1w, 2w, and 3w, with all predeclared ablations. The statistical
judge then applies the existing multiplicity procedure across the complete
evaluated family before the freeze-readiness gate runs.

## Boundaries
- Fresh Locked OOS remains unopened.
- V2 locked OOS is not used for tuning.
- No statistical threshold or minimum-sample rule is changed.
- No prior unfavorable result is discarded.
- A successful workflow is not equivalent to scientific freeze readiness.
