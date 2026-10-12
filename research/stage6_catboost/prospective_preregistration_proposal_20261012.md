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

## Operator-controlled sandbox and manifest contract

**The CLI now fails closed until all three explicit roots and a pinned
operator-audited manifest exist.** The roots must be absolute existing real
directories with no symlinked ancestors. Keep the input root and manifest root
read-only, and the output root separately writable; OS permissions (or a
container mount namespace) must physically deny any access to the reserved
Fresh Locked OOS dataset. Path words and an operator-provided hash are not
a security boundary against a malicious operator or race-prone filesystem.
Never set any of these roots to the full project repository or a broadly
accessible home directory.

The operator-audited manifest is a JSON object with **exactly** these keys:

- scope: development_validation_only
- source: immutable exchange/pair/timeframe identity, matching the data slice
- family: daily, weekly, or monthly
- slice_sha256: lowercase SHA-256 of the exact development JSON bytes
- source_interval_seconds: 3600 or 86400, matching the original provider audit
- first_open_timestamp, last_open_timestamp: canonical UTC *opening* times
- approved_dev_end_exclusive: audited exclusive availability boundary
- extraction_asof_timestamp: last available UTC extraction time
- source_audit_sha256: 64-hex SHA-256 of an independently preserved source audit

A reviewer must independently examine the raw source provenance, certify that
the physically extracted slice excludes all reserved windows, and record the
manifest SHA-256 **outside the input root** before authorizing any run. The
script validates the supplied digest, counts, alignment and cutoff but **cannot
prove that this review actually occurred**. Do not self-approve a manifest
using the historical observed diagnostics as independent new evidence.

A weekly prepared series can be backed by either audited hourly source bars
(168 per seven-day UTC week) or audited daily source bars (7 per week).
The exact source_interval_seconds from the approved manifest is propagated
into fold construction and repeated validation; the runner never silently
defaults a daily-source slice back to 3600 seconds. Full synthetic CLI
regressions cover both approved source cadences.

The three approved roots must be **pairwise disjoint**, not merely unequal:
neither input, output, nor manifest root may be an ancestor or descendant of
another. A nonblocking open plus regular-file fstat rejects FIFO/device input
without waiting for a writer. Those are defensive checks, **not** replacements
for OS mount/permission isolation, safe trusted manifests and race-safe
filesystem policy.

Every development candle must include exact complete OHLCV, a canonical UTC
bar-open timestamp, is_complete=true, and matching source_bars and
expected_source_bars equal to the number of source intervals in the actual
daily/weekly/monthly calendar period. No interpolation or source swapping.
A forecast that uses origin bar t's close is first available at the bar's
**end**, not at origin_timestamp (which denotes its opening). Report the
separate forecast availability and target maturity timestamps.

Both source and audit manifest are read and hashed from exactly one byte
buffer each, with symlinked parents refused. The output is created once
with exclusive permissions. Reports include code/data/manifest hashes,
runtime version, model settings and paired forecast/actual records. Any
unresolved provenance question is a NO-RUN blocker.

## Illustrative usage, AFTER out-of-band source audit

The values and roots below are placeholders: there is no approved actual
dataset or trusted manifest currently available for this PR.

    python scripts/challenger_v3_catboost_exploratory.py \
      --enable-exploratory \
      --approved-input-root /research/approved-dev-input \
      --input /research/approved-dev-input/btc_weekly.development.json \
      --approved-manifest-root /research/read-only-approved-manifests \
      --manifest /research/read-only-approved-manifests/weekly.audit.json \
      --approved-manifest-sha256 <approved-external-sha256> \
      --approved-output-root /research/only-exploratory-outputs \
      --output /research/only-exploratory-outputs/catboost_weekly.exploratory.json \
      --family weekly --horizon 1 --train-end 100 --stride 4 --max-folds 8

The placeholder boundary, stride and family must be prospectively frozen
before inspecting any genuinely independent outcomes. This runner is
**descriptive only**, caps evaluation at 12 folds (below the preliminary
20-independent-origin inferential threshold), and cannot authorize Stage 7
Freeze. Overlapping diagnostic targets are identified but not statistically
corrected. Whole-input continuity checks conservatively reject any slice with
a gap, including unrelated past gaps; any later change to eligibility must
be preregistered as a new experiment, never optimized post-hoc.

## Optional real-CatBoost integration check

For an *isolated, voluntary* synthetic-only smoke run, install a pinned
research-only CatBoost dependency (tested locally with catboost==1.2.8 on
Python 3.13). No change to pyproject.toml core dependencies; CI unit tests
mock the estimator by design. A standalone synthetic integration check must
verify the actual constructor, deterministic repeat runs, file suppression
and wall-clock time before research runs. Estimated work is capped at 12 ×
120 trees and one CPU thread, but this is not a measured runtime for real
data; no paid provider should be accessed.

**Original Stage-6 observed 24-family remains scientific NO-GO.**
