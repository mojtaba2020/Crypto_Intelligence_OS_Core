# Crypto Intelligence OS
## Backtesting Protocol v0.1

CONFIDENTIAL — INTERNAL USE ONLY

Version: 0.1
Purpose: Prevent self-deception, leakage, overfitting, unrealistic execution assumptions, and false trading edge.

---

# 1. Prime Rule

No rule, model, agent, prompt, indicator, or strategy is considered valuable because it looks good on historical data.

A component earns trust only after surviving:

1. Data integrity checks
2. Leakage controls
3. In-sample development
4. Out-of-sample testing
5. Walk-forward testing
6. Realistic execution simulation
7. Robustness testing
8. Paper trading
9. Ongoing live evaluation

Backtest performance is evidence.

It is NOT proof.

---

# 2. Research Separation

Every experiment must distinguish:

DEVELOPMENT DATA
and
EVALUATION DATA

Evaluation data must remain unseen during development whenever possible.

Do not repeatedly modify a strategy after looking at the same test period.

Once test data influences strategy design, that test set is no longer truly out-of-sample.

---

# 3. Time Integrity

Financial data must respect chronological order.

Future information must never influence past predictions.

Examples of prohibited leakage:

- Using tomorrow's price to generate today's signal
- Using future market-cap information
- Using full-dataset normalization before splitting
- Using indicators calculated with future observations
- Using news published after the decision timestamp
- Using revised historical data that was unavailable at the time
- Using final token supply information before it was known

All features must be point-in-time valid.

---

# 4. Point-in-Time Data Principle

For every prediction, the system should ask:

"What information was actually available at this exact timestamp?"

Store when possible:

- event timestamp
- publication timestamp
- retrieval timestamp
- data version
- source

Revised data must not silently replace historical information used in a past decision.

---

# 5. Train / Validation / Test Structure

For machine learning systems:

TRAIN
Used to fit model parameters.

VALIDATION
Used for model selection and tuning.

TEST
Used only for final evaluation.

The final test period should not be repeatedly inspected during development.

For time-series systems, random shuffling should generally be avoided.

Chronological splits are preferred.

---

# 6. Walk-Forward Evaluation

Preferred evaluation pattern:

Train
↓
Predict future period
↓
Advance time
↓
Retrain or update
↓
Predict next future period

Example:

2018–2021
Train

2022
Test

Then:

2018–2022
Train

2023
Test

Then:

2018–2023
Train

2024
Test

This better represents real deployment than a single historical split.

---

# 7. Purging and Embargo

When labels or features overlap across time boundaries,
training observations too close to the test period may leak information.

Where applicable use:

- Purging
- Embargo periods
- Leakage-aware cross-validation
- Walk-forward validation

Especially important when:

- labels span multiple bars
- forward returns are used
- rolling windows overlap
- event horizons overlap

---

# 8. Frozen Mojtaba Rules

Mojtaba Rules must be versioned before testing.

Example:

Mojtaba_Rule_1_v0.1

After a rule is tested, its historical definition must not be rewritten merely to improve historical performance.

If changed:

Create a NEW version.

Example:

v0.1
→ tested

v0.2
→ modified hypothesis

Never overwrite failed research history.

Failed hypotheses are valuable data.

---

# 9. Prediction Locking

Every live or forward prediction should be locked before outcome.

Record:

- prediction_id
- timestamp
- asset
- market regime
- direction
- time horizon
- confidence
- expected move
- entry zone
- invalidation condition
- model version
- agent version
- rule version
- data snapshot
- reasoning summary

After locking:

Prediction content becomes immutable.

Corrections require a new prediction record.

---

# 10. Human vs AI vs Hybrid Testing

When evaluating Human vs AI vs Hybrid:

Human Prediction:
Mojtaba produces independent forecast.

AI Prediction:
AI produces forecast without seeing Mojtaba's final answer.

Hybrid Prediction:
Human expertise and AI evidence are combined only after the independent forecasts exist.

Do not allow one prediction track to contaminate another.

All three must be timestamped.

---

# 11. Baselines Are Mandatory

Every proposed strategy must be compared against meaningful baselines.

Examples:

- Buy and Hold BTC
- Cash / no-trade
- Simple moving-average strategy
- Simple momentum strategy
- Equal-weight portfolio
- Random-direction control where appropriate

A complicated AI system that cannot outperform a simple baseline is not automatically valuable.

---

# 12. Execution Timing

Every backtest must explicitly define:

When is information observed?

When is the decision generated?

When can the trade actually execute?

Example:

Signal generated using candle close at 00:00

Trade cannot magically execute at the same closing price if that price was required to compute the signal.

Possible realistic execution:

Next bar open
or
next executable market price

Execution assumptions must be documented.

---

# 13. Trading Frictions

Backtests must include realistic trading costs.

Potential costs:

- Exchange fees
- Maker fees
- Taker fees
- Bid-ask spread
- Slippage
- Market impact
- Funding rates
- Borrow costs
- Gas fees where relevant
- Withdrawal / transfer costs where relevant

Always report:

Gross performance

AND

Net performance after costs

A strategy that works only before costs does not have proven economic edge.

---

# 14. Slippage Modeling

Slippage must not always be assumed constant.

Future versions should support:

- fixed basis-point slippage
- liquidity-dependent slippage
- volatility-dependent slippage
- order-size-dependent slippage

Stress test multiple slippage scenarios.

Example:

0 bps
5 bps
10 bps
25 bps
50 bps

If performance collapses under realistic slippage,
the strategy is fragile.

---

# 15. Market Liquidity Constraints

A backtest should not assume unlimited liquidity.

Before allowing a simulated trade:

Check:

- volume
- spread
- order-book depth where available
- trade size
- exchange liquidity

The system should eventually estimate:

Expected executable size

Expected slippage

Liquidity risk

---

# 16. Survivorship Bias

Historical crypto universes are especially vulnerable to survivorship bias.

Do NOT test only coins that survived until today.

Where possible include:

- failed projects
- delisted tokens
- inactive assets
- collapsed exchanges
- historical constituents

Otherwise the past may look artificially profitable.

---

# 17. Delisting and Failure Handling

If a token disappears, collapses, or is delisted:

The simulation must reflect the real historical consequence.

Do not simply remove bad assets from the dataset.

Examples:

- catastrophic loss
- inability to exit
- reduced liquidity
- delayed execution

These are part of real market risk.

---

# 18. Multiple Testing Problem

Testing hundreds of strategies increases the chance of finding a strategy that looks profitable by luck.

Record:

- number of hypotheses tested
- parameter combinations
- rejected models
- successful models

Do not report only the winner.

Future statistical controls may include:

- Deflated Sharpe Ratio
- Probabilistic Sharpe Ratio
- bootstrap analysis
- multiple-hypothesis corrections

The more strategies tested,
the stronger the evidence required.

---

# 19. Parameter Overfitting

Avoid searching thousands of parameters until historical results look perfect.

Example:

Do NOT choose:

RSI = 63
MA = 147
Stop = 3.27%

only because that exact combination maximized past return.

Prefer:

Stable parameter regions

over

One perfect historical point.

A robust strategy should work across reasonable neighboring values.

---

# 20. Sensitivity Testing

Every important parameter should be stress tested.

Example:

RSI threshold:

25
30
35

If performance only works at:

31.4

the system may be overfit.

Prefer wide stable performance regions.

---

# 21. Market-Regime Testing

Evaluate strategies separately during:

- Bull markets
- Bear markets
- Sideways markets
- High volatility
- Low volatility
- Liquidity crises
- Major news shocks
- Post-halving periods
- Pre-halving periods

Do not trust only full-period averages.

A strategy may be excellent in one regime and dangerous in another.

---

# 22. Asset Segmentation

Evaluate performance by asset category.

Examples:

- Bitcoin
- Ethereum
- Large-cap altcoins
- Mid-cap altcoins
- Small-cap tokens
- Meme coins
- DeFi
- Layer-1
- Layer-2

Do not assume a strategy transfers across asset classes.

---

# 23. Time-Horizon Segmentation

Evaluate predictions separately for:

- Intraday
- 1 day
- 3 days
- 1 week
- 1 month
- Cycle-level forecasts

Different agents may have different strengths at different horizons.

---

# 24. Core Trading Metrics

Minimum metrics should include:

- Total Return
- Annualized Return
- Sharpe Ratio
- Sortino Ratio
- Maximum Drawdown
- Volatility
- Win Rate
- Profit Factor
- Average Win
- Average Loss
- Expectancy
- Turnover
- Number of Trades
- Exposure
- Risk-adjusted return

Never evaluate using return alone.

---

# 25. Forecast Metrics

For non-trading forecasts evaluate:

- Directional Accuracy
- Mean Absolute Error
- Root Mean Squared Error
- Calibration
- Brier Score where applicable
- Confidence vs Accuracy
- Error by market regime

Confidence must be measured.

Example:

Predictions made at 80% confidence

should be correct approximately 80% of the time over a sufficiently large sample if calibration is good.

---

# 26. Confidence Calibration

Agents must not receive credit merely for sounding confident.

Track:

Confidence
vs
Actual correctness

Example:

Agent A:

90% confidence predictions
actual accuracy = 58%

This agent is overconfident.

Agent B:

70% confidence
actual accuracy = 69%

Agent B may be better calibrated even with similar raw accuracy.

---

# 27. Drawdown Analysis

Record:

- Maximum Drawdown
- Drawdown Duration
- Recovery Time
- Worst Trade
- Worst Week
- Worst Month

A profitable strategy with unacceptable drawdown may still be unusable.

---

# 28. Tail Risk

Evaluate extreme scenarios.

Examples:

- Exchange collapse
- Stablecoin depeg
- Flash crash
- Regulatory shock
- Weekend liquidity collapse
- Sudden liquidation cascade
- API outage
- Missing market data

Future versions should support scenario testing and stress simulation.

---

# 29. Randomization and Bootstrap Tests

Where appropriate:

- bootstrap trades
- randomize entry timing
- shuffle permitted components
- compare against randomized strategies

Goal:

Determine whether results may reasonably arise by chance.

---

# 30. Multi-Seed Evaluation

For stochastic systems:

Never trust one training run.

Use multiple random seeds.

Report:

- mean performance
- median performance
- variance
- worst run
- best run

A strategy that succeeds in one seed but fails in most others is unstable.

---

# 31. Agent Ablation Testing

For multi-agent systems, remove agents one at a time.

Example:

Full system:
Return = X

Without Narrative Agent:
Return = Y

Without On-Chain Agent:
Return = Z

This identifies whether each agent actually contributes value.

An agent that adds cost but no measurable improvement may be removed.

---

# 32. Model Ablation Testing

Compare:

Same strategy
+
Different foundation models

Example:

Model A
Model B
Model C

Evaluate:

- accuracy
- calibration
- cost
- latency
- consistency

Do not assume the newest or largest model is automatically best.

---

# 33. Prompt Evaluation

Prompt changes are experimental changes.

Example:

cycle_prompt_v1.0
vs
cycle_prompt_v1.1

A new prompt must beat the existing prompt on a held-out evaluation set before promotion.

---

# 34. Reproducibility

Every serious experiment should eventually record:

- experiment_id
- code version
- dataset version
- model version
- prompt version
- agent version
- configuration
- random seed
- start timestamp
- end timestamp
- cost assumptions
- execution assumptions
- results

Another researcher should be able to reproduce the experiment as closely as possible.

---

# 35. Experiment Registry

Every experiment receives a unique ID.

Example:

EXP-2026-0001

Store:

Hypothesis
Data
Configuration
Result
Interpretation
Decision

Possible decisions:

PROMOTE
RETEST
REJECT
ARCHIVE

Never delete failed experiments simply because they look bad.

---

# 36. Promotion Gates

A component may progress through:

IDEA
↓
RESEARCH
↓
HISTORICAL BACKTEST
↓
OUT-OF-SAMPLE
↓
WALK-FORWARD
↓
PAPER TRADING
↓
LIMITED LIVE TEST
↓
PRODUCTION

Skipping stages requires explicit justification.

---

# 37. Paper Trading Gate

Before real capital:

Run forward paper trading.

Compare:

Expected performance

vs

Actual forward performance

Evaluate:

- signal timing
- execution delay
- slippage
- missing data
- API errors
- model instability
- real-time behavior

Backtest success alone is insufficient.

---

# 38. Live Capital Rule

No autonomous agent receives unrestricted real-money control.

If live testing is eventually approved:

Start with limited capital.

Require:

- hard position limits
- hard loss limits
- kill switch
- human approval where required
- audit trail
- monitoring

Capital allocation should increase only after evidence accumulates.

---

# 39. Backtest Failure Is Valuable

Failed strategies must remain documented.

Failure database should eventually contain:

- failed hypotheses
- failed agents
- failed prompts
- failed models
- failed parameters
- reason for failure
- market regime
- lessons learned

Avoid repeating old mistakes.

---

# 40. Final Research Standard

A credible Crypto Intelligence OS result must answer:

What was known at decision time?

What was predicted?

When was it predicted?

What data was used?

What model was used?

What rules were active?

How would the trade really execute?

What costs were included?

What benchmark was used?

Was the result truly out-of-sample?

How many strategies were tested before finding this one?

Can the result be reproduced?

Does it survive different market regimes?

Does it survive realistic costs?

Does it survive forward testing?

If these questions cannot be answered,
the claimed edge is not yet trusted.

---

# Final Principle

Do not optimize the backtest.

Optimize the probability that the system survives reality.

CONFIDENTIAL — CRYPTO INTELLIGENCE OS
