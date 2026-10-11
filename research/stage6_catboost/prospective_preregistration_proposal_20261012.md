# Stage 6 CatBoost exploratory lane — prospective preregistration proposal

**Status: PROPOSAL ONLY / EXPLORATORY_ONLY / NO_FREEZE.**
The observed 2026-10-11 V3 24-hypothesis family remains NO-GO, with 0/24 Freeze-ready.
This proposal is not a retrospective registration of that family.

## Engineering contract
- New optional, opt-in file: scripts/challenger_v3_catboost_exploratory.py.
  Leave the frozen V3 statistical judge, observed 24-family, V1/V2 evidence,
  protected persistence baseline, and all production/locked artifacts unchanged.
- Accept only a physically pre-extracted **development/validation-only** slice,
  with exact JSON keys scope, source, candles, declared scope
  development_validation_only and a .development.json filename. **The tag and
  filename are assertions, not proof of provenance.** A human must audit the
  raw source, extraction cutoff and dataset identity before running.
- Refuse missing/incomplete candles, noncontiguous timestamps, invalid OHLCV,
  reserved/locked/OOS/production paths, and existing output files. No
  interpolation or cross-exchange candle copying to mask gaps.
- Features for t use bars through t; train labels must mature by t.
  Fresh model per fold, no shared fitted state or global fitted transforms.
- Fixed optional CatBoostRegressor: 120 trees, depth 4, rate 0.03,
  L2 4.0, seed 20261012, one CPU thread and no files written by the model.
  Up to 256 most recent mature training rows per fold (minimum 40).
- No more than 12 fold fits per invocation. At most 12 x 120 tree-builds
  single-threaded; this is a compute bound, **not** a measured time/cost.
  Time a small CPU smoke run and obtain approval before increasing budgets.
  No paid API, live providers, recurring jobs, model promotion or trading.
- Write only descriptive paired absolute-percentage-error comparison with
  persistence, EXPLORATORY_ONLY, NO_FREEZE, source and input SHA-256.
  No p-values or statistical superiority claims.

## Prospective registration required before independent assessment

1. **Provenance:** Independently audit exchange, raw fetch timestamps, exact
   source gaps, candle completeness, UTC convention, development-only cutoff,
   and immutable dataset/code SHA-256. Do not use unverified full-series files.
2. **Hypothesis:** Predeclare the exact family/horizon/feature mask and
   fixed estimator hyperparameters, loss metric and persistence comparator.
   Every new model, feature family, horizon or tuned configuration is another
   hypothesis, not a member of the already observed 24-family.
3. **Windows:** Freeze timestamp-based training, selection, diagnostic and
   genuinely untouched prospective evaluation windows. Purge target overlap;
   only labels mature by the corresponding origin are eligible. Reserved
   Fresh Locked OOS remains off limits without separate future authorization.
4. **Origins:** Fix cadence and gap/dependence treatment in calendar time.
   At least 20 independent eligible origins per registered hypothesis is
   a *preliminary* gate, subject to independent power review. If short,
   declare INELIGIBLE; never lower thresholds or invent/interpolate dates.
5. **Multiplicity:** Freeze the entire new hypothesis family and its
   multiplicity correction (e.g. Holm) before revealing fresh outcomes.
6. **Stopping criteria:** NO-GO for inconsistent source identity,
   incomplete/gapped candles, label overlap, feature leakage, insufficient
   independent observations, absent dependency, compute cap violations or
   unavailable truly untouched evaluation. No automatic champion or Freeze.
7. **Independent sign-off:** Data provenance, statistical and code reviewers
   approve the prospective plan, manifest hash, costs and blinding before
   any new evaluation. No automated merge, external expense or trading.

## Illustrative usage AFTER boundary audit

    python scripts/challenger_v3_catboost_exploratory.py \
      --enable-exploratory \
      --input /safe/research/btc_weekly.development.json \
      --output /safe/research/catboost_weekly.exploratory.json \
      --family weekly --horizon 1 --train-end 100 --stride 4 --max-folds 8

The values 100 and 4 are examples, not chosen data-dependent settings.
They must be prospectively frozen before any new independent analysis.
