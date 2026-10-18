# Stage-6: mock multi-feature Hybrid Ridge interface for all 13 horizon IDs

**DRAFT / synthetic-only / NO_RUN / NO_FREEZE / no trained real checkpoint.** Stacked on [Draft PR #94](https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/pull/94) SHA `9e45beb8f1eef87999914443ae8472073df9eefe`; that PR depends on Draft #93 -> #92 -> #91. No main changes or workflow activation.

## What this actually changes

The existing `crypto_intelligence_os.hybrid_forecasting.features` routine has **four feature group shapes** determined from completed *daily* observations: `all=12`, `no_halving=10`, `no_extrema=8`, `momentum_only=5`. It incorporates trailing daily log returns, 30-day realized volatility, 90/365-day range relationships and halving-calendar features. The existing `predict_hybrid` applies a **blend coefficient** to the `_estimate` ridge log-return before converting it into a price. PR #93's one-feature mock did not represent that true dimensionality or blend step.

The new `scripts/stage6_synthetic_multifeature_ridge_adapter.py`:

- Accepts only **64 KiB max caller-owned in-memory canonical JSON**, SHA-256 checked against a **caller-supplied** SHA. Classification `MOCK_MULTIFEATURE_ONLY`; `real_data_authorized=false`; no pickle/deserializer, file, URL, provider, model training, outcome, secret or arbitrary injected metadata.
- Demands exactly one **13-horizon state** per requested horizon: matching ordered feature-group names (12/10/8/5), each dimension's synthetic bounded weights/means/scales, a bounded 0..1 blend, *claimed* model-code digest, **claimed** last-resolved training target and model-creation times.
- For each horizon demands one closed-schema synthetic feature-value vector, claimed observed-at UTC after the synthetic origin bar is complete and no later than claimed issuance, and one existing two-bar synthetic window. Rejects reordered features, wrong dimensions, future-feature observation, post-origin training target and model-creation after forecast issue.
- Calls the **existing unmodified** `hybrid_forecasting._estimate` on mock multi-feature vectors; applies the existing model's `blend * signal` and ±1 log-return clip. Rejects nonfinite/subnormal lost terms and sign-erasing numerical cancellation. Feeds 13 point prices, up/down/flat and placeholder nested interval fields through the common PR #91 validator.
- Uses illustrative, **NOT calibrated**, 80%/95%-labelled ±5/±10% interval widths strictly as interface-test fixtures. Does not produce a real 13-horizon predictive model, valid trading signals, accuracy figures or empirical confidence intervals.
- Crucially, existing `train_hybrid` is a **DAILY** forecasting trainer with calendar-day targets. The mock input group dimensions are compatible with that daily feature equation, but **no evidence** exists that it trains 1h, 2h, 3h, 4h, 12h, 1w/2w/3w or 1mo/3mo models. Mock 13-horizon outputs must never be construed as genuinely trained versions for those temporal horizons.

## Acceptance, threat boundaries

Synthetic regression tests pin all four dimensions against the actual `features` code on **invented contiguous daily closes**; verify 13 complete forecast outputs, blend=0 flat, mock predictor arithmetic and calendar ordering; reject altered/duplicate JSON, missing/duplicate horizon, wrong feature names/groups/order, wrong dimensions, stale/late origin or feature observation, invented future labels/secrets, malformed coefficients and blend, false authorization and floating underflow.

**SHA-256 authenticates only the byte equality between the caller's bytes and its own claimed digest; not a vendor, historic origin, trained-state identity or independently witnessed first-availability.** Inputs are fully synthetic and timestamp claims self-authored. An independent custodian/license/runner/operator/reviewer per Issue #81 must separately approve any real-data model artifact workflow; protected OOS and real fitting remain off limits.

**Software acceptance:** Python 3.13/3.14 full GitHub CI, Ruff, mypy, pytest and independent Codex exact-head review. Keep Draft unmerged. Scientific Stage-6 **NO-GO / NO_RUN / NO_FREEZE**, V3 0/24 Freeze-ready.
