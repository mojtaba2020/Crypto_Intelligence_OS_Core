# Hourly Regime Research V1 — range_mean_6h at 12h

## Status

**No validated regime-specific edge was found.**

This is an exploratory research record, not a production signal.

## Data provenance

- Source: Bitstamp public BTC/USD hourly candles
- Validated archive artifact ID: `10915745274`
- Bars: **8,784 / 8,784**
- Period: 2024-01-01 00:00 UTC through 2024-12-31 23:00 UTC
- Continuity: PASS
- SQLite integrity: PASS

## Experiment

- Feature: `range_mean_6h`
- Forecast horizon: **12 hours**
- Model: Ridge alpha=1 with training-only z-score standardization
- Benchmark: Persistence
- Walk-forward train minimum: **720 hours**
- Test step: **24 hours**
- Walk-forward predictions: **336**
- Global statistical gate: paired moving-block bootstrap
- Regime statistical gate: **calendar-preserving moving-block bootstrap**
- Bootstrap repetitions: **10,000**
- Primary block length: **7 daily walk-forward observations**

## Global result

| Metric | Result |
|---|---:|
| Model MAPE | 1.14956% |
| Persistence MAPE | 1.16102% |
| Point-estimate improvement | +0.9867% |
| Direction accuracy | 55.65% |
| 95% bootstrap CI of paired loss improvement | [-0.00008015, +0.00030190] |
| Bootstrap probability improvement > 0 | 86.78% |
| Gate | **FAIL** |

The point estimate favored the model, but the confidence interval crossed zero.

## Point-in-time regime results

Regime definition: 24h trend band (up/range/down, +/-1% neutral threshold) crossed with trailing 24h realized volatility versus its point-in-time trailing median.

The regime bootstrap resamples contiguous blocks from the **full chronological daily walk-forward sequence** and preserves the regime indicator inside those blocks. This avoids pretending that irregularly spaced regime observations are adjacent in calendar time.

| Regime | Samples | MAPE improvement vs Persistence | Direction accuracy | 95% calendar-preserving CI | P(improvement > 0) | Decision |
|---|---:|---:|---:|---|---:|---|
| down__high_vol | 64 | +0.7188% | 59.38% | [-0.00047710, +0.00061920] | 62.03% | FAIL |
| down__low_vol | 36 | +3.4581% | 61.11% | not gated (<40) | — | INSUFFICIENT_SAMPLES |
| range__high_vol | 38 | -2.9872% | 44.74% | not gated (<40) | — | INSUFFICIENT_SAMPLES |
| range__low_vol | 81 | +0.3420% | 53.09% | [-0.00023850, +0.00032198] | 58.65% | FAIL |
| up__high_vol | 65 | +1.9142% | 56.92% | [-0.00021652, +0.00068338] | 83.88% | FAIL |
| up__low_vol | 52 | +0.9154% | 57.69% | [-0.00030548, +0.00049377] | 67.46% | FAIL |

## Scientific interpretation

- No regime with enough samples passed the improved 95% calendar-preserving bootstrap gate.
- The stronger dependence-aware method widened several intervals, but **did not change the scientific conclusion**.
- `down__low_vol` remains an exploratory hypothesis only because it had just 36 samples; its apparent +3.46% improvement must not be treated as evidence of a real edge.
- `range__high_vol` was worse than Persistence in the point estimate.
- Because six regimes were inspected after the global candidate was selected, the exploratory table is not a confirmatory multiple-comparison result.
- The one follow-up hypothesis (`down__low_vol`) is preregistered before accessing independent confirmation data.
- The confirmatory plan now treats **2023 as primary** and **2025 as replication**, with no threshold tuning allowed on either dataset.

## Engineering notes

During local verification, a floating-point edge case was found in the volatility split: effectively equal near-zero volatilities could be separated by numerical noise. The classifier was stabilized with a negligible tolerance. The real Bitstamp regime assignments and research conclusions were unchanged after the fix.

A locked confirmation runner now rejects any archive overlapping the 2024 exploratory period, and the confirmatory statistical gate preserves calendar dependence.

## Decision

`range_mean_6h` is **not promoted** to a validated 12h signal.

Keep `down__low_vol` only as a preregistered independent-test hypothesis. If the primary 2023 confirmation fails, retire `range_mean_6h` as an active 12h candidate rather than retuning it on the failed period.
