# Stage-6 synthetic-only bridge: existing hybrid Ridge inference → 13-horizon contract

**2026-10-17 / DRAFT ENGINEERING / NO_RUN / NO_FREEZE.** This is stacked on the current [Draft PR #92](https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/pull/92) exact head `32a8717e81624dc66db2666866637dca5a481672`, itself stacked on PR #91. Neither parent PR is merged. No GitHub workflow is edited.

## The engineering advance

This explicitly imports and calls the unchanged **existing production-research numerical inference equation** `crypto_intelligence_os.hybrid_forecasting._estimate`. It does **not** copy the equation, train a Ridge model, infer any real market outcome or access private/new market data.

- Fixed input: **exactly 13 synthetic two-bar windows**, already checked for contiguous exact hourly/daily/Monday-weekly/calendar-month cutoffs, synthetic observation times and issuance before target.
- Fixed MOCK model state: **one scalar feature and two frozen mock coefficients**, with one `weights`/[bias, slope], `means`, `scales`, and well-formed *self-claimed* SHA-256 for each of the 13 horizons.
- Feature: synthetic one-bar log price change, using `log1p` for close prices to preserve near-equal differences.
- Calls the project's existing `_estimate(weights, means, scales, (feature,))` for each synthetic horizon, clips the resulting mock log-return to ±20%, turns it into a mock point-price forecast and implied direction, and hands exactly 13 records to the independently reviewed PR #91 output validator.
- The 80%/95% interval fields are still **arbitrary ±5%/±10% integration placeholders**; there is **NO empirical calibration or coverage proof**. No actual forecasts, saved model artifacts, model evaluation, competition outcome or real-data/historical feature table is produced.
- Mock weights were authored for synthetic unit tests; **there are NO trained 13-horizon Ridge states**. Do NOT call this a production Ridge model or proof of predictive skill. Claim-only SHA-256 and timestamp fields are NOT cryptographic custody or evidence of real historical issuance.

## Why this is meaningfully closer to the eventual model

The former PR #92 has two deliberately simple toy calculations without connecting to the repository's trained-model inference path. This bridge now tests the **same pure equation already used by the project's hybrid research model** through the common 13-horizon downstream output contract. With no real fit it can validate software shape, calendar continuity, type/finite checks and the exact final record interface. It cannot select a winner or supply real features, fitted coefficients, uncertainty calibration, defensible precision metrics or actual forecast origins.

Tests exercise every horizon, the exact existing `_estimate` output on mock coefficients, rising/down/flat, impossible state scales/weights, missing model or future-outcome fields, custom state mappings, late source-observation claims, huge/subnormal price rounding, and scientific NO_RUN flags. Inference functions never perform network or file operations.

## Future gated integration (not authorized here)

Real model integration would require provenance-attested, dated and *externally authorized* model states built from strictly point-in-time permissible features/labels and a frozen signed origin calendar. Need independent A1–A6 evidence, source/legal rights, physically isolated runner, and a separate operator/reviewer authorization under [Issue #81](https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/issues/81). Real fit, locked OOS, backtest selection, production publishing and trading remain out of scope.

**Engineering acceptance:** GitHub CI both Python 3.13 and 3.14 and fresh exact-head independent Codex review; no merge unless human signs off. Scientific Stage-6 V3 0/24 Freeze-ready, **NO-GO / NO_RUN / NO_FREEZE**.
