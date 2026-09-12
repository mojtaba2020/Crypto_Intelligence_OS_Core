# Crypto Intelligence OS — Agent Architecture v0.1

CONFIDENTIAL — INTERNAL USE ONLY

## Mission

Build a coordinated AI research and decision system for crypto markets.

Agents do not make final financial decisions.
They collect evidence, analyze specialized domains, challenge assumptions, and report to the orchestration layer.

---

## Command Structure

Founder / Human Decision Layer
        ↓
Chief Intelligence Orchestrator
        ↓
Specialist Agent Teams
        ↓
Evidence + Scores + Conflicts
        ↓
Hybrid Decision Engine
        ↓
Human Review

---

## Core Agent Team

### 1. Market Regime Agent
Purpose:
Identify the current market environment.

Inputs:
- Price
- Volume
- volatility
- trend
- BTC dominance
- market breadth

Possible outputs:
- Bull
- Bear
- Sideways
- Transition
- High-risk regime

---

### 2. Technical Analysis Agent
Purpose:
Evaluate market structure and momentum.

Future inputs:
- Moving averages
- RSI
- momentum
- volume
- support/resistance
- volatility
- trend structure

---

### 3. Cycle Intelligence Agent
Purpose:
Test Bitcoin cycle hypotheses.

Responsibilities:
- Halving timing
- cycle tops
- cycle bottoms
- drawdowns
- duration analysis
- compare historical cycles

This agent must test Mojtaba Rules rather than assume they are correct.

---

### 4. On-Chain Intelligence Agent
Purpose:
Analyze blockchain activity.

Future inputs:
- exchange flows
- wallet activity
- realized metrics
- holder behavior
- whale movements
- network activity

---

### 5. Tokenomics Agent
Purpose:
Analyze supply-side risk.

Future inputs:
- circulating supply
- total supply
- FDV
- unlock schedules
- inflation
- team allocation
- investor allocation

---

### 6. Narrative & Sentiment Agent
Purpose:
Detect market narratives and social momentum.

Future inputs:
- news
- social activity
- search interest
- developer activity
- narrative acceleration

---

### 7. Liquidity & Market Quality Agent
Purpose:
Determine whether a token is realistically tradable.

Future inputs:
- volume
- order-book depth
- spreads
- exchange coverage
- liquidity concentration

---

### 8. Scam & Risk Agent
Purpose:
Search for structural and fraud-related risks.

Future checks:
- suspicious contracts
- ownership concentration
- unlocked supply
- admin privileges
- liquidity risk
- abnormal wallet behavior
- misleading project claims

---

### 9. Opportunity Ranking Agent
Purpose:
Combine validated evidence and rank opportunities.

It must never rank a project only because one signal is strong.

Future output example:

Opportunity Score: 0–100
Risk Score: 0–100
Confidence: 0–100

---

### 10. Devil's Advocate Agent
Purpose:
Try to prove the current thesis wrong.

Responsibilities:
- Search for contradictory evidence
- Identify confirmation bias
- Challenge Mojtaba
- Challenge other AI agents
- Identify missing data

This agent is mandatory before high-confidence conclusions.

---

## Chief Intelligence Orchestrator

The Orchestrator does NOT blindly average agent opinions.

Responsibilities:

1. Assign tasks
2. Collect evidence
3. Detect disagreement
4. Request additional research
5. Evaluate source quality
6. Send structured results to the Hybrid Decision Engine

---

## Human vs AI vs Hybrid

For selected forecasts:

### Human
Mojtaba creates an independent forecast.

### AI
The AI system creates an independent forecast without seeing Mojtaba's final answer.

### Hybrid
The system combines human domain expertise with machine evidence.

All three forecasts must be timestamped before the outcome is known.

---

## Agent Output Standard

Every agent should eventually return:

- Conclusion
- Confidence
- Evidence
- Data source
- Counterargument
- Risk factors
- Missing information
- Timestamp

No agent may output only:

BUY
SELL
HOLD

without supporting evidence.

---

## Safety Rule

Agents are research and decision-support systems.

No autonomous real-money trading will be enabled until:

- extensive backtesting
- out-of-sample validation
- paper trading
- risk controls
- human approval

are completed.

---

## Development Status

v0.1 — Architecture defined.
No claim is made that all listed agents are currently implemented.

CONFIDENTIAL — Crypto Intelligence OS
