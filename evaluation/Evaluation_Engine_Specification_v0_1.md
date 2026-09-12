# Crypto Intelligence OS
## Evaluation Engine Specification v0.1

CONFIDENTIAL — INTERNAL USE ONLY

Version: 0.1

Purpose:

Build a provider-neutral, evidence-driven evaluation system capable of measuring
Humans, AI models, Agents, Prompts, Tools, Rules, and Hybrid Intelligence.

No component receives permanent trust.

Every component must continuously earn its place through measurable performance.

---

# 1. Prime Directive

Crypto Intelligence OS must never select an AI model, agent, prompt,
tool, or strategy because:

- It is new
- It is popular
- It is expensive
- It has a famous provider
- It performs well on vendor benchmarks
- Internet opinion says it is the best

Components are promoted only when they demonstrate measurable improvement
on Crypto Intelligence OS evaluations.

---

# 2. Evaluation Philosophy

Evaluation must occur at multiple levels.

LEVEL 1
Component Evaluation

LEVEL 2
Agent Evaluation

LEVEL 3
Workflow Evaluation

LEVEL 4
Prediction Evaluation

LEVEL 5
Portfolio / Market Outcome Evaluation

LEVEL 6
Human vs AI vs Hybrid Evaluation

A system can succeed at one level while failing at another.

---

# 3. Evaluation Objects

The Evaluation Engine should eventually evaluate:

- Foundation models
- AI agents
- Prompts
- Tools
- MCP tools
- Data providers
- Market rules
- Mojtaba Rules
- Quantitative models
- Machine-learning models
- Agent workflows
- Orchestrators
- Model routers
- Human forecasts
- AI forecasts
- Hybrid forecasts

Everything important must be measurable.

---

# 4. Provider-Neutral Evaluation

Evaluation must not be structurally tied to one AI provider.

Possible competitors may include:

- OpenAI
- Anthropic
- Google
- Chinese frontier models
- Open-source models
- Future providers

The evaluation interface should treat them as replaceable candidates.

Conceptually:

evaluate(
    task = "cycle_analysis",
    candidate = model_X
)

Then compare candidate performance against currently deployed systems.

---

# 5. Blind Model Evaluation

Whenever practical, model evaluations should be blinded.

The evaluator should not know which provider produced the result.

Example:

Candidate A
Candidate B
Candidate C

NOT:

OpenAI
Claude
Gemini

until scoring is complete.

Goal:

Reduce brand bias.

---

# 6. Evaluation Dataset

Crypto Intelligence OS should maintain proprietary evaluation datasets.

Dataset categories may include:

- Historical Bitcoin cycles
- Bull markets
- Bear markets
- Sideways periods
- Liquidity crises
- Major crashes
- Halving periods
- Altcoin rotations
- Token unlock events
- Narrative shifts
- Exchange failures
- Scam events
- Stablecoin crises
- Regulatory shocks
- Market manipulation cases

Evaluation datasets should become strategic proprietary assets.

---

# 7. Dataset Splits

Evaluation data should be separated into:

DEVELOPMENT SET

Used during development.

VALIDATION SET

Used when comparing alternatives.

HIDDEN TEST SET

Not used during system development.

LIVE FORWARD SET

Generated from future real-world predictions.

Repeated exposure to hidden evaluation data destroys its value.

---

# 8. Temporal Integrity

Because crypto is a time-series domain,
evaluation must preserve chronological integrity.

Future information must not appear in historical evaluation context.

Every evaluation example should define:

decision_timestamp

data_cutoff_timestamp

outcome_timestamp

All information supplied to an evaluated system must have existed before
the defined cutoff.

---

# 9. Point-in-Time Evaluation

Each historical evaluation should reconstruct:

"What could the system actually have known at that moment?"

Avoid:

- Future news
- Revised historical data
- Future token supply data
- Future market-cap data
- Future exchange listings
- Future social information

Historical hindsight must never become artificial AI intelligence.

---

# 10. End-State Evaluation

Evaluate whether the agent ultimately achieved the desired result.

Examples:

Was the market regime correctly identified?

Was the token-risk assessment correct?

Was the requested research completed?

Was the forecast properly structured?

Was the correct tool output obtained?

Outcome success matters.

---

# 11. Trajectory Evaluation

The Evaluation Engine must also inspect HOW an agent reached its result.

Possible questions:

Did it choose the correct tool?

Did it call unnecessary tools?

Did it repeatedly retry?

Did it retrieve relevant evidence?

Did it ignore contradictory information?

Did it misuse a tool?

Did it hallucinate evidence?

Did it perform unnecessary agent handoffs?

Did it respect permissions?

A correct final answer produced through an unsafe or unreliable process
should not receive full credit.

---

# 12. Trace Evaluation

Agent runs should eventually generate evaluation traces.

Trace elements may include:

trace_id

agent_id

model_id

prompt_version

tool_calls

handoffs

retrievals

guardrail_events

errors

retries

latency

token_usage

cost

final_output

evaluation_result

This allows forensic analysis after failures.

---

# 13. Grading Methods

Different tasks require different graders.

Possible grading methods:

DETERMINISTIC GRADER

CODE-BASED GRADER

REFERENCE-ANSWER GRADER

STATISTICAL GRADER

RULE-BASED GRADER

LLM-AS-JUDGE

PAIRWISE COMPARISON

HUMAN REVIEW

MARKET-OUTCOME GRADER

No single grader is appropriate for every task.

---

# 14. Deterministic Graders

Use deterministic grading whenever possible.

Examples:

Correct mathematical calculation

Correct JSON schema

Correct API parameter

Correct market return

Correct drawdown

Correct prediction timestamp

Correct data cutoff

Correct asset identifier

If code can objectively determine correctness,
prefer code over an LLM judge.

---

# 15. LLM-as-Judge

LLM judges may be useful for:

- Research quality
- Evidence quality
- Reasoning completeness
- Thesis clarity
- Counterargument quality
- Source relevance

But LLM judges must not be treated as perfect.

Potential judge problems:

- Provider bias
- verbosity bias
- style bias
- position bias
- self-preference
- inconsistent scoring

Important evaluations may require:

multiple judges
or
human calibration.

---

# 16. Judge Calibration

Before trusting an AI judge:

Compare its scores with expert human judgments.

Measure agreement.

If the judge systematically disagrees with human evaluation,
recalibrate or replace it.

Judge models must also earn trust.

---

# 17. Pairwise Evaluation

When comparing models or agents,
pairwise evaluation may be preferable.

Example:

Output A
vs
Output B

Question:

Which provides stronger evidence,
better risk analysis,
and fewer unsupported claims?

Randomize output order to reduce position bias.

---

# 18. Multi-Trial Evaluation

AI systems are stochastic.

Never judge important systems from one run.

Run multiple trials.

Possible metrics:

Mean score

Median score

Standard deviation

Failure rate

Worst-case performance

Best-case performance

Consistency

A model that occasionally produces brilliant output but frequently fails
may be worse than a slightly weaker but highly reliable model.

---

# 19. Statistical Confidence

Evaluation results should eventually report uncertainty.

Examples:

Accuracy = 72%

95% confidence interval = X–Y

Do not treat small benchmark differences as meaningful without sufficient evidence.

Example:

Model A = 74.1%

Model B = 74.4%

This may not represent a real advantage.

---

# 20. Infrastructure Noise

Evaluation systems must recognize environmental noise.

Possible sources:

- API latency
- Tool downtime
- rate limits
- network failure
- different compute environments
- data-provider differences
- caching
- sandbox configuration

Model performance should not be confused with infrastructure differences.

---

# 21. Agent Success Metrics

Agent scorecards should eventually include:

Task success

Accuracy

Confidence calibration

Evidence quality

Tool-selection accuracy

Tool-call success rate

Unsupported-claim rate

Hallucination rate

Retry rate

Latency

Cost

Safety violations

Source quality

Consistency

---

# 22. Market Prediction Metrics

For market predictions evaluate:

Directional Accuracy

Forecast Error

Confidence Calibration

Brier Score

Maximum Adverse Excursion

Maximum Favorable Excursion

Expected vs Actual Return

Risk-adjusted return

Drawdown

Regime-specific accuracy

Time-horizon accuracy

---

# 23. Market-Regime Evaluation

Performance must be segmented by market regime.

Example:

Cycle Agent

Bull Market Accuracy: 77%

Bear Market Accuracy: 59%

Sideways Accuracy: 48%

Transition Accuracy: 68%

One overall accuracy number can hide dangerous weaknesses.

---

# 24. Asset-Specific Evaluation

Agents may perform differently across assets.

Evaluate separately where appropriate:

Bitcoin

Ethereum

Large-cap altcoins

Mid-cap altcoins

Small-cap tokens

Meme coins

DeFi

Layer-1

Layer-2

Other categories

Do not assume Bitcoin expertise transfers to all crypto assets.

---

# 25. Horizon-Specific Evaluation

Track performance separately for:

1 hour

4 hours

1 day

3 days

7 days

30 days

90 days

Cycle-level forecasts

An agent may be strong long-term and poor short-term.

---

# 26. Human Evaluation

Mojtaba's forecasts must be evaluated with the same rigor as AI.

No preferential treatment.

Measure:

Accuracy

Calibration

Risk assessment

Market-regime performance

Time-horizon performance

Asset-specific performance

Human expertise is treated as measurable intelligence.

---

# 27. AI Evaluation

AI predictions should record:

model

model_version

agent

prompt_version

tools

data cutoff

confidence

forecast

outcome

This enables performance comparison across model generations.

---

# 28. Hybrid Evaluation

The central question is:

Does Hybrid Intelligence outperform Human-only and AI-only intelligence?

For comparable predictions evaluate:

Human

vs

AI

vs

Hybrid

under identical:

asset

timestamp

data availability

forecast horizon

evaluation method

---

# 29. Incremental Value

A new component must demonstrate incremental value.

Example:

System without On-Chain Agent:

Accuracy = 64%

System with On-Chain Agent:

Accuracy = 67%

Then evaluate:

Is the improvement statistically meaningful?

Does it justify added cost?

Does it improve all regimes or only one?

Does it introduce new failure modes?

Components that add complexity without measurable benefit should be removed.

---

# 30. Ablation Testing

Remove components individually.

Example:

Full system

Then test:

Without Cycle Agent

Without Narrative Agent

Without Devil's Advocate

Without On-Chain Agent

Without Mojtaba Rules

Compare results.

This reveals which components actually create value.

---

# 31. Devil's Advocate Evaluation

Even the Devil's Advocate Agent must be evaluated.

Metrics may include:

Useful contradiction rate

False objection rate

Important risk detection

Missed risk rate

Impact on final decision accuracy

Generating objections is not enough.

The objections must improve decisions.

---

# 32. Model Router Evaluation

The Model Router itself must be evaluated.

Question:

Did it choose the best model for the task?

Metrics:

Routing accuracy

Task success

Cost savings

Latency savings

Fallback success

Provider concentration

The router must not become an untested source of error.

---

# 33. Cost-Normalized Evaluation

Best quality is not always the best production choice.

Possible metric:

Quality per dollar

Example:

Model A:

Score = 95
Cost = $1.00

Model B:

Score = 93
Cost = $0.08

For some tasks Model B may be preferable.

The router should consider quality thresholds.

---

# 34. Latency Evaluation

Measure:

Time to first useful output

Total task completion time

Tool latency

Model latency

Workflow latency

Research tasks may tolerate slower models.

Real-time systems may not.

---

# 35. Reliability Evaluation

Measure:

Success rate

Timeout rate

Tool failure rate

Schema failure rate

Invalid output rate

Fallback rate

Crash rate

A brilliant system that fails frequently is not production-grade.

---

# 36. Hallucination Evaluation

Track unsupported claims.

Possible categories:

Invented data

Invented source

Incorrect number

Incorrect token information

Incorrect date

Unsupported conclusion

Fabricated market event

Severity should be recorded.

Financial-domain hallucinations require strict evaluation.

---

# 37. Source Quality Evaluation

Evidence should be scored by source reliability.

Potential hierarchy:

Primary source

Official blockchain data

Exchange data

Established data provider

Reputable journalism

Secondary analysis

Social media

Anonymous claims

Agent confidence should decrease when evidence quality is weak.

---

# 38. Evidence Coverage

Evaluate whether conclusions are actually supported.

A high-quality output should connect:

CLAIM
↓
EVIDENCE
↓
SOURCE
↓
TIMESTAMP

Unsupported claims should reduce score.

---

# 39. Contradiction Detection

Evaluate whether agents detect conflicting evidence.

Example:

Technical Agent:
Bullish

On-Chain Agent:
Bearish

Narrative Agent:
Bullish

Liquidity Agent:
Weak

The system should not silently average these outputs.

It should identify the conflict.

---

# 40. Confidence Calibration

Agents must be rewarded for calibrated confidence.

Example:

Agent predicts 100 events at approximately 70% confidence.

Approximately 70 should succeed over a sufficiently large sample
if calibration is accurate.

High confidence with poor accuracy is a major failure.

---

# 41. Overconfidence Penalty

Strong confidence should carry greater penalty when incorrect.

An agent that repeatedly outputs:

95% confidence

while being correct only 60% of the time

should lose trust rapidly.

---

# 42. Safety Evaluation

Agent systems must be tested for unsafe behavior.

Examples:

Attempting unauthorized actions

Exceeding permissions

Ignoring human approval

Accessing unnecessary tools

Executing risky commands

Exposing secrets

Autonomous trading without authorization

Safety failures can override performance improvements.

---

# 43. Blast-Radius Evaluation

Evaluate:

If this agent fails,
what damage could occur?

Possible levels:

LOW

MEDIUM

HIGH

CRITICAL

Higher-risk capabilities require stronger controls and human approval.

---

# 44. Adversarial Evaluation

Create cases designed to break the system.

Examples:

Misleading news

Fake social narratives

Conflicting data

Missing data

Extreme volatility

Token ticker collisions

Manipulated volume

API corruption

Prompt injection

Malicious tool output

Agents must survive hostile conditions.

---

# 45. Tool-Use Evaluation

For each agent evaluate:

Did it select the correct tool?

Did it supply correct arguments?

Did it interpret results correctly?

Did it call unnecessary tools?

Did it fail gracefully?

Did it verify suspicious tool output?

Tool use is part of intelligence.

---

# 46. MCP Tool Evaluation

MCP-connected tools should be tested independently.

Evaluate:

Schema correctness

Permission boundaries

Latency

Reliability

Version compatibility

Error handling

Security behavior

Agents should not automatically trust every connected MCP server.

---

# 47. Prompt Evaluation

Every production prompt is versioned.

Example:

cycle_agent_prompt_v1.0

cycle_agent_prompt_v1.1

Before replacement:

OLD PROMPT
vs
NEW PROMPT

Run the same evaluation suite.

Promote only when evidence supports the change.

---

# 48. Regression Testing

Every major system update must rerun core evaluations.

A change that improves one capability may damage another.

Example:

New model improves research quality

but

reduces tool reliability.

Regression tests prevent silent degradation.

---

# 49. Golden Evaluation Set

Maintain a stable set of high-quality cases.

These cases become the permanent regression suite.

Examples:

BTC cycle analysis

Major historical crash

Token unlock analysis

Scam detection

Bull-to-bear transition

False narrative event

Conflicting agent evidence

Tool failure

Low-liquidity token

The golden set should evolve carefully.

---

# 50. Hidden Evaluation Set

Some evaluation cases should remain hidden from development workflows.

Purpose:

Reduce benchmark overfitting.

If developers and agents repeatedly see every test,
they may optimize specifically for the evaluation rather than reality.

---

# 51. Evaluation Contamination

If evaluation examples become part of:

training

prompt development

manual tuning

agent memory

they may no longer represent unbiased evaluation.

Contaminated datasets should be marked.

---

# 52. Live Canary Evaluation

New models or agents may initially receive a small fraction of real workflows.

Example:

95% Current Production

5% Candidate

Compare:

Quality

Cost

Latency

Errors

User outcomes

before increasing deployment.

---

# 53. Shadow Evaluation

A new candidate may run silently beside production.

Production makes the real decision.

Candidate makes an independent shadow decision.

Later compare outcomes.

This allows real-world testing without operational risk.

---

# 54. Champion vs Challenger

Maintain:

CHAMPION

Current production component.

CHALLENGER

Candidate replacement.

A Challenger must beat the Champion under defined promotion rules.

Brand reputation does not matter.

---

# 55. Promotion Gates

Candidate lifecycle:

EXPERIMENTAL
↓
OFFLINE EVALUATED
↓
HIDDEN-SET PASSED
↓
SHADOW MODE
↓
LIMITED DEPLOYMENT
↓
PRODUCTION

Promotion requires documented evidence.

---

# 56. Automatic Rejection Conditions

Candidate may be rejected immediately for:

Critical safety failure

Severe hallucination

Data leakage

Unauthorized action

Prediction contamination

Unacceptable reliability

Broken traceability

Evaluation manipulation

---

# 57. Evaluation Registry

Every evaluation experiment receives an ID.

Example:

EVAL-2026-000001

Record:

evaluation_id

candidate

baseline

dataset_version

grader_versions

number_of_trials

metrics

cost

latency

result

decision

notes

---

# 58. Evaluation Reproducibility

A serious evaluation must record:

Code version

Dataset version

Model version

Prompt version

Agent version

Tool version

Environment

Configuration

Random seed where applicable

Evaluation time

Grader version

This allows later reconstruction.

---

# 59. Evaluation Decision

Possible decisions:

PROMOTE

KEEP_CURRENT

RETEST

LIMITED_DEPLOYMENT

REJECT

ARCHIVE

Every decision should include a reason.

---

# 60. Continuous Evaluation

Production systems should continue generating evaluation data.

Real failures should automatically become candidates for future tests.

Loop:

Production Failure
↓
Failure Analysis
↓
New Evaluation Case
↓
Regression Suite
↓
System Improvement

The evaluation system should become stronger after every meaningful failure.

---

# 61. Frontier Model Adoption Rule

A newly released frontier model is NOT immediately promoted.

Procedure:

New Model
↓
Offline Evaluation
↓
Domain Evaluation
↓
Agent Evaluation
↓
Cost / Latency Evaluation
↓
Safety Evaluation
↓
Shadow Testing
↓
Promotion Decision

This applies to every provider.

---

# 62. Model Retirement Rule

A deployed model may be removed if:

A challenger significantly outperforms it

Reliability deteriorates

Cost becomes unjustified

Provider availability declines

Security concerns emerge

Better alternatives exist

No model has permanent ownership of a role.

---

# 63. Evaluation Dashboard

Future interface should display:

Human Score

AI Score

Hybrid Score

Agent Scores

Model Scores

Market-Regime Scores

Calibration

Cost

Latency

Failure Rate

Trend Over Time

Users should be able to see how intelligence quality changes.

---

# 64. Long-Term Intelligence Score

Future versions may produce a composite score.

Conceptual example:

Intelligence Score =
Accuracy
+ Calibration
+ Evidence Quality
+ Reliability
+ Risk Awareness
+ Cost Efficiency
+ Robustness

Weights must themselves be validated.

Never hide individual metrics behind only one final score.

---

# 65. Long-Term Data Moat

Evaluation history becomes proprietary intelligence.

Over time Crypto Intelligence OS should know:

Which model is strongest for each task.

Which Agent works in each regime.

Which Mojtaba Rules create real edge.

When human judgment beats AI.

When AI beats human judgment.

When Hybrid Intelligence creates additional value.

Which prompts fail.

Which tools fail.

Which market conditions cause errors.

This knowledge becomes difficult for competitors to copy.

---

# Final Standard

Crypto Intelligence OS does not ask:

"Which AI model is famous today?"

It asks:

"Which intelligence source has proven itself for this exact task,
under this exact market regime,
at this required level of reliability,
cost, latency, and risk?"

---

# Final Principle

NO MODEL WITHOUT EVALUATION.

NO AGENT WITHOUT MEASUREMENT.

NO CONFIDENCE WITHOUT CALIBRATION.

NO DEPLOYMENT WITHOUT EVIDENCE.

CONFIDENTIAL — CRYPTO INTELLIGENCE OS
