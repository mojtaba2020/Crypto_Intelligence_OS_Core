# Multi-Timeframe Research Contract V1

This contract extends the hourly research laboratory without weakening the scientific rules already used by Judge V3.

## Scope

Promotion-grade forecast horizons:

- Hourly: 1h, 2h, 3h, 4h, 12h
- Daily: 1d, 2d, 3d
- Weekly: 1w, 2w, 3w
- Monthly: 1mo, 3mo

Long-cycle comparison horizons:

- 2y, 3y, 4y, 5y, 6y, 7y, 8y

The multi-year horizons are **not promotion eligible** in V1. Bitcoin has too few independent long cycles for a statistically reliable Champion/Challenger promotion decision at those horizons. They are retained for descriptive cycle research, hypothesis generation, and comparison only.

## Locked scientific rules

1. Candidate selection is performed on training/validation data only.
2. Locked out-of-sample data must not be used for feature selection, hyperparameter search, or model-family choice.
3. A locked set that has already influenced research decisions is never treated as pristine again.
4. Every promotion-grade horizon uses a point-in-time-safe walk-forward evaluation.
5. Dependence is handled with a predeclared moving-block bootstrap appropriate to the horizon family.
6. Multiple comparisons are controlled within each declared family with Holm-Bonferroni.
7. A favorable point estimate alone is never sufficient for promotion.
8. Prospective confirmation and independent-exchange replication are mandatory before registry promotion.
9. No workflow success status is interpreted as model superiority.
10. Automatic production promotion remains disabled.

## Horizon-specific research

The same model and feature set are not copied blindly across horizons.

Hourly research emphasizes microstructure-like OHLCV behavior, short momentum/mean reversion, volatility, candle structure, and volume interaction.

Daily and weekly research may add multi-scale trend, volatility regime, drawdown, range compression/expansion, and market-state persistence.

Monthly research may add longer trend, cycle position, drawdown depth/duration, and multi-month volatility state.

Multi-year research may use halving distances, historical top/bottom spacing, cycle ratios, drawdown structure, and time-in-price-range statistics, but remains descriptive until the amount of independent evidence is sufficient for promotion-grade inference.

## Execution order

1. Freeze the completed hourly Stage Zero result.
2. Build shared point-in-time resampling and dataset contracts for 1d, 1w, and 1mo.
3. Add horizon-specific Feature V3 modules.
4. Run validation-only model tournaments per family.
5. Apply family-specific statistical Judge and Regime Gate.
6. Run prospective confirmation.
7. Replicate on an independent exchange.
8. Register only dual-confirmed challengers.
9. Connect only registry-approved Champions to live forecast output.

This design shares infrastructure while keeping statistical boundaries separate for each horizon family.
