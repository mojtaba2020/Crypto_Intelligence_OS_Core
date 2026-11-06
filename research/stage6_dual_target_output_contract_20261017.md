# Stage-6 13-horizon dual-target output contract (2026-10-17)

**DRAFT / OFFLINE SYNTHETIC ONLY / NO_RUN / NO_FREEZE.** This code does not fetch BTC data, train a model, issue live forecasts, access any locked OOS, score outcomes, alter a scheduler, or deploy anything.

## Concrete engineering gap addressed

Existing Draft PR #80 already proposes *calendar feasibility* and as-of metadata gates on a stacked research branch. This independent, small Draft is instead an **output interface** for all thirteen requested prediction horizons:

1h, 2h, 3h, 4h, 12h; 1d, 2d, 3d; 1w, 2w, 3w; 1mo and 3mo.

For each synthetic record validate:

- canonical UTC origin and exact future target end, with Monday ISO-week starts and **real calendar month lengths**;
- actual claimed issuance must be strictly **after** origin cutoff and **before** future target end. This does not prove when any prediction was really issued;
- explicit BTCUSD market identity, independent model/feature/manifest *claimed SHA-256* fields;
- strictly positive finite origin and predicted USD point prices;
- exact **up/down/flat** equality policy: a predicted unchanged price must be **flat**, not up;
- the declared 80% interval must enclose the price forecast and nest within the 95% interval; these labels are nominal, not calibrated coverage claims;
- reject all unknown price-target outcomes, target labels, performance fields, secrets, or partial schemas before any report;
- deterministic **local, self-generated SHA-256** for normalized report integrity, NOT an exchange receipt, signature, external timestamp, immutable custody, approval, or privacy protection.

The batch gate rejects **missing, extra or duplicate** horizons and sorts the exact thirteen into canonical order. No fail-open partial success; all outputs expressly say **scientific_authorization=NO_RUN**, **stage7_freeze_authorized=False**, **forecast_issuance_authenticated=False**, **source_vintage_authenticated=False** and **forecast_accuracy_evaluated=False**.

## Caution / scientific exclusions

This is an interface validator, **not** an implemented 13-horizon forecasting model, market-data coverage proof, statistically calibrated interval, live publication guard, backtest performance result, 90% accuracy assertion, or independently held audit artifact. A caller can forge timestamps, input prices or SHA digests. Independent producer/custodian/reviewer A1-A6 in [Issue #81](https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/issues/81) and pre-registered research design in [Issue #78](https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/issues/78) remain mandatory before any real-data run.

This standalone draft is based on main and does **not** cherry-pick or alter PR #80, the older eight family studies, frozen 24-hypothesis results or any live GitHub workflow. No expense or external data.

## Gate before any engineering acceptance

Full CI on Python 3.13 and 3.14, followed by independent Codex adversarial review at the **exact final head**. Keep Draft, no merge, no live execution and no OOS.