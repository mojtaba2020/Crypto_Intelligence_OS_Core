# Stage-6: two synthetic comparator adapters for all 13 forecast horizons

**2026-10-17 · DRAFT · INACTIVE · SYNTHETIC / NO_RUN / NO_FREEZE.**

This stacked branch builds on the exact [PR #91 output-contract head](https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/pull/91) `84c23451dfadbce32e0eec3f34370039598c8da6`. It does not change or activate the current live Bitcoin runner, Cron, model selection, data sources, frozen experiments, OOS or trading.

## What is actually wired

A pure function `build_synthetic_comparator_batches(windows, model_code_sha256)` maps 13 strictly typed, user-supplied **synthetic** two-bar windows to both:

- **Persistence**: target-price prediction equals the last completed bar's synthetic close, so the price-implied direction is always `flat` under the exact-zero rule.
- **One-bar momentum**: extrapolates the two known synthetic close prices via a bounded log-return multiplied by the **number of target-family bars**, with an illustrative ±20% cap. This is not fitted, tuned, calibrated or a claim of forecasting skill.

One window per exact 13-horizon ID is required. Every window must use adjacent *canonical UTC bar cutoffs* (hourly, daily, Monday-weekly, first-of-calendar-month) with strict claimed observation/issuance times **after source completion and before target maturity**. Earlier stored values, old price observations and hashes are **self-declared**, not third-party attested.

Both adapters send all 13 of their records through PR #91's `validate_full_13_horizon_batch` for the shared exact schema, direction, price, nested 80/95-labelled intervals, normalized self-hash, no unexpected outcome fields and fail-closed complete batch logic. They accept **only Python `list` and plain `dict`** containers; custom mapping/list subclasses are excluded to reduce type-based validation bypasses. All forecasts have distinct claimed model SHA strings supplied by caller. Those are not authenticated hashes of this source code or actual trained artifacts.

**Illustrative, NOT calibrated intervals:** symmetric ±5% for the field labelled 80% and ±10% for the field labelled 95%. They are placeholders solely to exercise the output API. **Do not present them as probabilistic 80%/95% coverage**, meaningful predictive uncertainty or user-ready investment advice. No volatility regime, sample dependence or temporal calibration is estimated.

## Safety and acceptance boundaries

- No data fetch, filesystem operation, provider request, paid agent, model fitting/scoring, protected/locked OOS access, real-money trading, export, workflow dispatch or upload.
- Strictly synthetic fixtures include rising, falling, unchanged, missing/duplicate horizons, noncanonical weekly/monthly origin, nonadjacent bars, late source observation, issuance at target close, NaN/Inf, oversized prices, forged hash formats, outcome-field smuggling, disallowed venues, custom mapping/list and invalid intervals.
- The result **always** includes `scientific_authorization=NO_RUN`, `stage7_freeze_authorized=False`, `real_data_evaluated=False`, `forecast_issuance_authenticated=False`, `interval_80_95_calibrated=False`, `candidate_superiority_evaluated=False`, `locked_oos_access=False`.
- **This is not a 13-horizon production engine.** It is one deterministic synthetic adapter set; no historical/forward performance has been observed. The real 13-horizon model comparison and empirical uncertainty calibration need predeclared methods and independently approved point-in-time development datasets under [Issue #78](https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/issues/78) and [Issue #81](https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/issues/81).

**Quality gate:** exact-head Python 3.13/3.14 Ruff+mypy+pytest+quality CI, then independent Codex P0–P2 adversarial review. Keep PR Draft/unmerged even when software checks pass.
