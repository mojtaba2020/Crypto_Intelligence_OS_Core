# Mojtaba Rules Engine — v0.1

Private proprietary market hypotheses and decision rules for Crypto Intelligence OS.

## Purpose

This document stores Mojtaba's market hypotheses and trading logic.

These rules are NOT assumed to be true.
Every rule must be tested using historical data, out-of-sample validation, and later paper trading before being trusted.

---

## Rule 1 — Bitcoin Four-Year Cycle Hypothesis

### Hypothesis
Bitcoin appears to follow an approximate four-year market cycle.

Observed structure:

- Approximately 1 bearish phase
- Approximately 3 bullish / recovery / expansion years

### Status
Hypothesis — requires quantitative backtesting.

### Future Tests
- Measure cycle duration
- Identify bull and bear phases objectively
- Compare all historical Bitcoin cycles
- Test whether the pattern remains statistically useful

---

## Rule 2 — Halving Timing Hypothesis

### Hypothesis
Major Bitcoin market bottoms and tops may occur within a recurring timing window relative to Bitcoin halvings.

Working range:

- Bear-market bottom: approximately 500–550 days before a halving
- Bull-market top: approximately 500–550 days after a halving

### Status
Hypothesis — not yet validated.

### Future Tests
- Calculate exact days between historical bottoms, tops, and halvings
- Measure average and standard deviation
- Test whether the relationship is statistically meaningful
- Evaluate whether the timing window changes across cycles

---

## Rule 3 — Bear-Cycle Drawdown Compression

### Hypothesis
Bitcoin bear-cycle percentage drawdowns may be decreasing over successive cycles.

Working assumption:

Each major bear cycle may experience approximately 5–7 percentage points less drawdown than the previous major bear cycle.

### Status
Hypothesis — requires historical verification.

### Future Tests
- Measure peak-to-bottom drawdown for every major cycle
- Compare drawdown reduction between cycles
- Test linear and nonlinear decay models
- Estimate uncertainty ranges

---

# Core Research Principle

Mojtaba Rules are hypotheses, not market truths.

The system must never modify historical predictions after outcomes become known.

Every rule should eventually be evaluated using:

- Historical backtesting
- Out-of-sample testing
- Live paper trading
- Error measurement
- Confidence calibration
- Maximum drawdown
- Risk-adjusted performance

---

# Human vs AI Framework

Each important market forecast may eventually be generated independently by:

1. Mojtaba
2. AI
3. Mojtaba + AI Hybrid

Predictions must be timestamped and locked before the outcome is known.

Performance will later determine which intelligence source performs best under different market regimes.

---

CONFIDENTIAL — INTERNAL USE ONLY
Crypto Intelligence OS
