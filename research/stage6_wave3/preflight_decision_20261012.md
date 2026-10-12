# Stage-6 Wave-3: synthetic preflight and research decision record

**2026-10-12 · STATUS = ENGINEERING PREFLIGHT ONLY · SCIENTIFIC NO-GO · 0/24 Freeze-ready**

This document is **not** a prospective statistical registration, not an approved
dataset, and not an authorization for market-data training or inference.
Keep PR #73 Draft and existing V3 judge, historical 24-hypothesis family,
protected persistence baseline, and reserved Fresh Locked OOS unchanged.

## Evidence ledger (no outcome selection)

- Pinned scientific base: `15cca84587df7fd77d2e237da3bea959f61bac6a`.
- Conditional CatBoost software-GO: `7f28ce70e370eccefaec913afba9d47df4b11342`;
  source branch `research/stage6-catboost-exploratory-20261012`,
  [draft PR #73](https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/pull/73).
- Archived original Wave-3 independent-worker outputs:
  [AUDIT-03](https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/issues/74#issuecomment-6131600604),
  [STATS-03](https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/issues/75#issuecomment-6131601724),
  [FEATURE-03](https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/issues/76#issuecomment-6131602438).
  Real session UUID and token/cost telemetry were not exposed; do not invent them.
- These are distinct *proposals* made independently. They do NOT form a
  mutually approved prospective hypothesis or valid evidence of accuracy.

## Numerical-correctness correction after independent review (2026-10-13)

An independent Codex review of head `bcfb562a10a3db99221c14031d12bed98f4901f6`
reported **P2 / NO-GO for the isolated synthetic preflight**: subtracting
separately rounded `log(C_i)` values can produce a false zero for distinct
adjacent floating-point closes. The original ordinary-price test suite (536
passing full-suite tests at that prior head) did not catch this issue.

The subsequent code correction determines the strict direction of each
mathematical log-return by direct ordering of previously validated positive
closes: `C_i > C_(i-1)` (up), `C_i < C_(i-1)` (down), equality (zero).
The logarithm is strictly increasing for positive prices, so this preserves
the exact **sign** needed by `1(r_i*r_(i-1)<0)` without subtracting rounded
logarithms. No return magnitudes are used or approximated. The rest of the
frozen weighting definition and bounds remain unchanged.

The new synthetic numeric suite asserts alternating one-ULP prices really
produce seven reversals (including small/large magnitudes), exact ties never
count as reversals, uneven volume weights remain correct, and 256 seeded
near-ULP windows match an independent comparison-based reversal oracle.
**These tests cannot establish market-data provenance or performance.**
Independent **post-fix** CodeX review is still required for synthetic
engineering GO; this is a correction, not a GO claim.

## Integer precision correction after the second independent NO-GO (2026-10-13)

An independent Codex review of the previous numerical-fix head
`4bdc80126da5595755cf95d952f95ddf2efadb98` found **P2 / NO-GO**
for this **isolated synthetic preflight**. The original code accepted integer
prices but converted them into floating-point before the sign comparison.
For `a = 2**53`, `b = a + 1`, `float(a) == float(b)`, making seven
true alternating price reversals falsely produce a zero share.

The revised validator retains the original exact integer/finite-float values
during OHLC bounds checking and close-order comparisons. It rejects bool and
non-finite floats. Volume weights are accumulated with exact rational
arithmetic (`fractions.Fraction`) to avoid silent large-integer rounding,
overflow from float conversion, or weight cancellation. Only the final
bounded dimensionless fraction is converted into the public float result.

New synthetic regression coverage includes the original `2**53 + 1`
counterexample, ties and mixed int/float price windows, enormous integer
prices/volumes, invalid OHLC boundaries one integer apart, boolean/inf
rejection, and 256 deterministic mixed-numeric windows with an independent
rational weighted-oracle. These tests do not verify any dataset, feature
accuracy, source provenance or physical filesystem isolation.

**A green CI result alone remains insufficient for software GO.** Obtain
a *new* independent adversarial Codex review on the final post-fix commit.
Neither software signoff nor real-data readiness is presumed here. Stage-6
scientific **NO-GO / NO_FREEZE / 0 of 24** remains unchanged.

## What this branch actually introduces

- A **pure** deterministic Python function for the one fixed FEATURE-03
  "daily volume-supported reversal share" formula with exactly nine complete
  trailing daily bars and seven adjacent-return comparisons.
- Unit tests using **only synthetic OHLCV**, covering known output values
  (0, 1, fractional), future-data mutation, volume scale invariance, zero
  returns, zero denominator, exact source cadence, finalization/availability
  cutoff, UTC alignment, corrupt bars, unit consistency, and strict gap rejection.
- The new function is **not imported by CatBoost, not added to an ablation,
  not wired to a runner, not allowed to access market data, and not enabled
  by default**. A successful synthetic test is NOT a performance claim.
- Input fields `source_bars`, `expected_source_bars`, `is_complete`,
  `volume_unit`, and `source_finalized_at` are checked as supplied
  assertions. They are **not forensic evidence** of provider integrity,
  ingestion history, completeness or source revisions. Independent source
  audit and trusted read-only data boundaries remain mandatory.

## Unresolved *design differences*: STOP before outcome inspection

| Dimension | STATS-03 proposal | FEATURE-03 proposal | Decision |
| --- | --- | --- | --- |
| Forecast horizon | 1 daily bar | 7 daily bars | **Unselected** |
| Feature history | New 29-bar short-history protocol | Keep established 365-bar daily eligibility | **No gate reduction approved** |
| Candidate | Fixed 1d CatBoost short-history candidate | Existing feature set vs one added scalar | **Neither experimental comparison authorized** |
| Inference | Prospective one-member hypothesis, effect/power TBD | Descriptive paired comparison; up to 24 model fits suggested | **No inference; >12-fit request rejected** |
| Availability | End of bar + independently established ingestion publication | Same, including finalized volume unit and history | **Independent source timestamp audit missing** |

Do **not** choose between horizons based on old diagnostics or silently merge
these separate designs. Engineering unit tests on FEATURE-03 have no bearing on
which scientific plan will be preregistered; no model performance was assessed.

## Hard blockers and required sequence

1. **External provenance and isolation:** AUDIT-03's unresolved requirements:
   auditable read-only input/manifest mounts, immutable trusted reviewer
   authorization of source/extraction SHA, reserved-data denial including aliases,
   race-resistant ancestors, publishing/revision/availability time, frozen
   runnable image/dependencies, and controlled entry point. **No actual dataset
   is certified or accessible by this preflight**.
2. **Calendar + independent sample feasibility:** Establish a label-blind,
   timestamp-level origin eligibility ledger, without scanning reserved
   outcomes; determine if an untouched, truly prospective period is available.
   Invalid scheduled origins stay invalid; do not interpolate/replenish them.
3. **Single future preregistration:** After provenance and feasibility signoff,
   independently preregister exactly one hypothesis (or declare NO-RUN),
   date boundaries, feature mask, horizon, comparison, alpha/multiplicity,
   mature-label purge/embargo, lag/revision availability, fixed inference
   algorithm, economic effect threshold, dependence-sensitive 80%-power
   calculation and the required independent N.
4. **Compute safety:** Existing exploratory contract caps **12 fits × 120
   trees**, one CPU thread, per invocation. FEATURE-03's 24-fit paired
   suggestion is **not authorized**, and concatenating separate capped runs
   does not create valid confirmation. Any new plan requires explicitly
   approved separate budget and preregistration.
5. **Review + permission:** Independent technical/statistical signoff before
   any proposed research-data evaluation. No access to Fresh Locked OOS, paid
   provider API, recurring workflow, trade, auto-merge, production launch or
   Stage-7 Freeze.

**Current decision: only deterministic, synthetic-only feature preflight
is permitted. A scientific claim, champion selection, or deployment is not.**
