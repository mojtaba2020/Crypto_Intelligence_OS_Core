# Five-model BTC/USD four-hour competition — observed retrospective run

**Run**: [GitHub Actions #43989038450](https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/actions/runs/43989038450) — completed successfully.

**Scope**: EXPOSED October 2026 retrospective development exploration, **NOT**
a live forward forecast, untouched OOS experiment, promotion or trading signal.
Data were fetched on **2026-11-17 00:37:29.251806 UTC** (November 16, 2026,
6:37:29 PM CST / Houston). Historical features' original first-public timestamps
and subsequent revisions have **not** been independently authenticated.

Public source: Coinbase Exchange BTC-USD, 1-hour close/BTC volume and
5-minute close target. Predeclared window: **2026-10-01T00:00:00Z** through
**2026-10-18T00:00:00Z exclusive**. This interval was previously observed by
the project, so its outcomes cannot be treated as fresh independent confirmation.

## Data and coverage

- Canonical four-hour origins: **102 expected, 102 complete**.
- Fully historical, expanding-window evaluation: **24** scored origins.
- Prior targets must finish **before** an evaluated origin's timestamp.
- Five fit candidates and one no-fit Persistence baseline; fixed hyperparameters.
- Raw exchange bars were fetched at run time; no fabricated issuance or original
  publication receipts and no historical forecast ledger entries were produced.
- The scoring metric is mean absolute **log-price** error, not percentage-of-
  trades profitability. Direction counts exclude strictly flat cases.

| Model | Mean absolute log error | Mean paired gain vs Persistence | Correct direction |
|---|---:|---:|---:|
| Persistence | **0.00540936** | +0.00000000 | Not defined |
| Elastic Net | 0.00560612 | -0.00019675 | 11 / 24 |
| Ridge | 0.00563447 | -0.00022511 | 9 / 24 |
| Extra Trees | 0.00566141 | -0.00025205 | 8 / 24 |
| Histogram Gradient Boosting | 0.00569509 | -0.00028573 | 9 / 24 |
| Random Forest | 0.00592466 | -0.00051530 | 11 / 24 |

**Observed result**: No fitted candidate beat Persistence on the specified
24 exposed historical development origins. Elastic Net had the lowest price
error among the fitted models but **is not a scientifically approved winner**.
No future forecast accuracy, statistical alpha or prospective advantage was
established. Small, dependent, overlapping origins forbid naive p-values.

## Audit digests (reported by run)

- Hourly (canonical UTC, close, volume):
  `d4491d4cec87f6f11558f86488722950a164defa292583f4914358f57fbf5f29`
- 5-minute (canonical UTC, close, volume):
  `3976586c468ec3424ff612be3392a722cb61eae2f397041def5cc8410b0fca16`

GitHub artifact ID **14286313562**, name
`btc4h-five-model-oct2026-retrospective-json`; retention 14 days.
This report preserves the exact key results after artifact expiration.
The recorded hash is reproducibility metadata for files read at this run,
not third-party first-availability attestation.

## Release decision

**NO_PROMOTION / NO_FREEZE / NO_TRADE.** Leave rolling BTC4h, Cloudflare,
the frozen formal 30-day experiment and all historical ledgers unchanged.
Next science gate: genuinely prospective, identical-origin, precommitted
comparisons with verified source availability and statistically adequate
mature outcomes, not tuning against this same visible October sample.
