# Post-confirmatory decision: range_mean_6h / down__low_vol / 12h

Date: 2026-09-27

## Locked primary result

The preregistered 2023 Bitstamp primary confirmation executed without changing the locked hypothesis, model, regime, threshold, walk-forward design, benchmark, loss, bootstrap method, or acceptance threshold.

- Validated hourly bars: 8,760 / 8,760
- Missing bars: 0
- Continuity: PASS
- SQLite integrity: PASS
- Ingestion chain of custody: PASS
- Independent-period guard: PASS
- Canonical data SHA-256: `150f9c5a315f95051511236a4caed14630936390eb16302be9f07480caaba32e`
- Target-regime samples: 28
- Preregistered minimum target-regime samples: 40
- Decision: `INSUFFICIENT_SAMPLES`

Because the preregistered minimum sample gate was not reached, the primary bootstrap significance gate was not evaluated. This result is neither a confirmatory pass nor a statistical confirmatory fail.

## Scientific handling

1. Freeze the 2023 primary result exactly as observed.
2. Do not relax the regime definition, minimum-sample threshold, model, feature, horizon, benchmark, loss, scaling, walk-forward design, bootstrap settings, or seed in response to the 2023 result.
3. Do not pool 2023 with another period post hoc to manufacture a primary pass.
4. Preserve 2025 as the already-preregistered replication period.
5. Execute 2025 with the same locked hypothesis and evaluation semantics, but label it replication rather than a replacement primary test.
6. A 2025 replication pass cannot by itself promote the feature because the preregistration requires replication in addition to a primary pass.
7. A 2025 result may be used to decide whether the hypothesis merits a new, separately preregistered future study; any such study must use untouched future/independent data and must not rewrite the 2023 decision.
8. The preregistration file itself remains unchanged after confirmatory-data access.

## Current status

`PRIMARY_INCONCLUSIVE_INSUFFICIENT_SAMPLES__REPLICATION_ALLOWED_NO_PROMOTION`
