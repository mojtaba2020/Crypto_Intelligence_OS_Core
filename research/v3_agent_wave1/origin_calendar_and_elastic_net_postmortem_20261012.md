# Stage-6 origin-calendar integrity and Elastic Net postmortem

**Classification: exploratory investigation of already observed development/validation evidence. NOT a new training result, independent validation, statistical rejection, or Freeze authorization.**

## Evidence and provenance
- Successful historical full-family workflow [38106402242](https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/actions/runs/38106402242); artifact ID `11691222113`; archive SHA-256 `eecb5202dc1cbfb45e82531fb43e6655df4a5a176e23d34b1b0d0cf048addbbf`.
- Its source-fetch job `114372766470` records **Bitstamp native-daily 5,516 rows over 5,520 expected dates, four missing daily intervals / four gaps**; Bitfinex native daily contains **7 missing dates / one gap**. This does not establish that each specific missing day can safely be replaced.
- The project requires continuous point-in-time feature history: `has_valid_feature_history` in `scripts/multitimeframe_features_v3.py`. Longest feature histories are **365 daily bars** and **52 weekly bars**. `is_temporally_valid_sample` also requires a mature, continuous target.
- One source-day gap can therefore invalidate **up to 365 following daily forecast origins** (and the week containing it, plus a further trailing year of weekly feature origins). This is a mathematical consequence of the declared contiguous-window policy, **not a claim that 390–420 days of source candles were missing**.
- Never backfill a source date with an interpolated price, copy cross-exchange candles under the original exchange identity, or use a locked period to increase model sample counts.

## Exact gaps among observed development forecast origins

These are gaps **between evaluated forecast origins**, not equivalent to missing raw source intervals:

| Horizons | Evaluated origins per horizon | Declared origin step | Calendar gaps in evaluated origins | Missing scheduled origin positions per horizon |
|---|---:|---:|---|---:|
| 1d, 2d, 3d | 51 | 30 days | Three gaps of 390 days each | 36 |
| 1w, 2w | 46 (1w), 45 (2w) | 28 days | 420 and 392 days | 27 |
| 3w | 44 | 28 days | Two gaps of 420 days | 28 |

Daily gaps (each horizon): **2017-01-14 → 2018-02-08**, **2019-10-31 → 2020-11-24**, **2022-07-17 → 2023-08-11**.

Weekly gaps (1w, 2w): **2019-09-30 → 2020-11-23** and **2022-07-04 → 2023-07-31**. For 3w the second gap begins **2022-06-06** and ends **2023-07-31**.

The 4 ablations within each horizon have identical origin calendars; all six horizons and 24 rows were covered. This is **not** evidence that the existing moving-block bootstrap p-values are wrong, but calendar discontinuities and time-dependence assumptions deserve independent review before considering the inference trustworthy for promotion.

## Elastic Net 1w: how robust is the apparent signal?

The nested **`1w x regime_only_delta`** candidate selected on earlier origins was `elastic_net`. On **19 later diagnostic forecast origins**:

- Persistence-minus-model mean APE difference: **+0.004531249924** (about **0.453 percentage points**, descriptive).
- Lower model APE on **10 origins**; higher APE on **9 origins**.
- Median paired improvement: **+0.001189770743**.
- Remove the **three largest positive improvements** as a descriptive concentration stress check: mean becomes **−0.002239512804**.
- **Ineligible for the prespecified primary 20-origin inference**, raw p conservatively set to 1, Holm reject = false; no claim of statistical significance, superiority, or Freeze readiness.

Importantly, a development diagnostic chosen after seeing this result **cannot become untouched independent confirmation simply by rerunning Elastic Net**. Keep this finding tagged `exploratory`.

## Actionable Stage-6 research work (scientifically controlled)

1. **Provenance root-cause check**: use source fetch audit to identify exact missing Bitstamp dates and why they were absent. Separate provider missing history from true market absence or exchange downtime. Validate same-exchange source independently; never silently synthesize/backfill a candle.
2. **Calendar-dependent inference check**: independent statistics review of origin-block bootstrap with gaps of 392–420 calendar days. Document assumptions and effects without changing the original predeclared judge or using observed results to shop for favorable p-values.
3. **Future candidate plan**: pre-register a clean, genuinely different feature-history protocol (e.g. shorter trailing history) **as a new experimental hypothesis**, including full family, new dataset fingerprints, untouched evidence plan, budget and failure criteria. It must NOT be described as rescuing or confirming the previously observed 24 hypotheses.
4. **No-go remains**: 0/24 freeze-ready in the old development family; do not open Fresh Locked OOS, relax sample-size/Holm criteria, claim a champion, or promote a model.

## Implementation-note
A local read-only diagnostic reconstructed the 24 nested selected candidates, 19-origin Elastic Net paired differences, six origin calendars and the gap schedule directly from the pinned eight-file archived artifact. Synthetic fixture/tampering checks (8/8) passed locally; **do not claim CI coverage for this diagnostic unless it is committed and CI completes**.
