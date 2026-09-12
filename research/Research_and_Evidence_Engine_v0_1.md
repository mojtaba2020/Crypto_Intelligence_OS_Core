# Crypto Intelligence OS
## Research & Evidence Engine v0.1

CONFIDENTIAL — INTERNAL USE ONLY

Version: 0.1
Status: REVIEWED ARCHITECTURE BASELINE

Purpose:

Design a provider-neutral research and evidence system that converts
external information into structured, traceable, time-aware evidence
without confusing:

FACT
with
INFERENCE
with
OPINION.

The Research & Evidence Engine exists to answer:

WHAT DO WE KNOW?

HOW DO WE KNOW IT?

WHEN DID WE KNOW IT?

HOW RELIABLE IS THE EVIDENCE?

WHAT CONTRADICTS IT?

WHAT IS STILL UNKNOWN?

---

# 1. Prime Directive

Crypto Intelligence OS must never treat:

search results

AI summaries

social posts

news headlines

agent statements

or repeated claims

as automatically true.

The system must construct an evidence chain:

CLAIM
    ↓
EVIDENCE
    ↓
SOURCE
    ↓
TIMESTAMP
    ↓
PROVENANCE
    ↓
VALIDATION
    ↓
CONFIDENCE

If the chain is weak:

The conclusion must remain weak.

---

# 2. Evidence Before Conclusion

Research workflow should generally be:

Question
    ↓
Research Plan
    ↓
Source Discovery
    ↓
Source Retrieval
    ↓
Source Validation
    ↓
Fact Extraction
    ↓
Claim Construction
    ↓
Contradiction Search
    ↓
Evidence Synthesis
    ↓
Uncertainty Assessment
    ↓
Evidence Package
    ↓
Decision System

Do not begin with a desired conclusion
and search only for supporting evidence.

---

# 3. Architectural Position

Conceptual flow:

User / Orchestrator Objective
        ↓
Research Planner
        ↓
Source Discovery Layer
        ↓
Retrieval Layer
        ↓
Source Validation
        ↓
Extraction Layer
        ↓
Claim-Evidence Layer
        ↓
Contradiction Engine
        ↓
Source Quality Assessment
        ↓
Evidence Synthesis
        ↓
Evidence Package
        ↓
Agents / Hybrid Engine / Risk Engine

---

# 4. Provider Neutrality

Research must not depend permanently on one:

Search engine

AI provider

News provider

On-chain provider

Market-data provider

Browser system

Research API

Potential sources may change over time.

Use adapters behind stable interfaces.

Conceptually:

research.search()

research.fetch()

research.verify()

research.extract()

research.build_evidence()

Provider-specific behavior remains behind adapters.

---

# 5. Research Objective Contract

Every serious research run should define:

research_id

objective

research_question

asset

time_horizon

decision_timestamp

data_cutoff_time

required_evidence_types

minimum_source_quality

freshness_requirement

risk_class

maximum_cost

maximum_latency

stopping_rule

This prevents open-ended research from drifting.

---

# 6. Research Question Decomposition

Complex questions should be decomposed.

Example:

"Is Token X a high-quality investment candidate?"

Subquestions may include:

Identity

Tokenomics

Liquidity

On-chain behavior

Security

Team

Technology

Adoption

Narrative

Unlock schedule

Counterparty risk

Market structure

Contradictory evidence

Research plans should be explicit.

---

# 7. Search Is Discovery, Not Evidence

A search result is not automatically evidence.

Search engines may provide:

Titles

Snippets

Rankings

Summaries

Cached text

These are discovery mechanisms.

Important claims should preferably be verified
against the underlying source.

---

# 8. Source Hierarchy

Source quality depends on the claim.

Potential hierarchy:

PRIMARY SOURCE

Examples:

Blockchain data

Official filing

Protocol documentation

Official governance proposal

Original research paper

Exchange announcement

Regulator publication

Company disclosure

Canonical source code repository

---

DIRECT DATA PROVIDER

Examples:

Exchange market feed

On-chain dataset

Verified API

---

HIGH-QUALITY SECONDARY SOURCE

Examples:

Established financial publication

Professional research organization

Independent technical analysis

---

SECONDARY ANALYSIS

Examples:

Industry commentary

Research blogs

Analyst reports

---

SOCIAL / COMMUNITY SOURCE

Examples:

X

Reddit

Telegram

Discord

Forums

Useful for:

Narratives

Sentiment

Discovery

Not automatically authoritative for factual claims.

---

# 9. Claim-Dependent Authority

No source is universally authoritative.

Example:

For protocol code behavior:

Source code may be strongest.

For regulatory action:

Regulator publication may be strongest.

For market price:

Exchange / market data may be strongest.

For community sentiment:

Social platforms may be directly relevant.

Source quality must depend on the claim being evaluated.

---

# 10. Source Registry

Each source should eventually receive:

source_id

source_type

publisher

domain

author where available

publication_time

event_time where available

retrieval_time

update_time

canonical_url

jurisdiction where relevant

language

license

content_hash where possible

archive_reference

reliability_profile

---

# 11. Source Identity

Do not count mirrored or copied content
as independent sources.

Example:

Article A

Article B

Article C

all copy:

Original Press Release D

Independent evidence count:

1 primary lineage

not:

4 confirmations.

---

# 12. Evidence Lineage

Every claim should preserve lineage.

Example:

CLAIM-00021
    ↓
SOURCE-001
    ↓
Official Token Unlock Schedule
    ↓
retrieved_at
    ↓
content_hash

A future researcher should be able to reconstruct
where the claim originated.

---

# 13. Point-in-Time Research

Historical research must respect:

WHAT WAS AVAILABLE THEN.

Do not allow modern information to leak backward.

For every source track where possible:

event_time

publication_time

retrieval_time

revision_time

Historical backtesting must only use evidence
available before the prediction cutoff.

---

# 14. Event Time vs Publication Time

These are different.

Example:

Exchange exploit occurred:

02:14 UTC

Official announcement:

03:05 UTC

System discovered announcement:

03:07 UTC

A prediction at:

02:45 UTC

must NOT use the 03:05 announcement.

---

# 15. Revision Awareness

Web pages and reports may change after publication.

Where important:

Preserve historical version or snapshot.

Track:

original publication

revision

correction

retraction

updated timestamp

Do not silently apply modern revisions to historical predictions.

---

# 16. Freshness Classification

Possible states:

REAL_TIME

FRESH

ACCEPTABLE

STALE

VERY_STALE

UNKNOWN

Freshness expectations depend on data type.

Example:

BTC executable price:
seconds

Breaking news:
minutes

Token unlock schedule:
hours / days

Protocol documentation:
possibly months

Historical halving date:
stable

---

# 17. Freshness Requirement

Each research task should define
how fresh evidence must be.

A high-quality but stale source may be inappropriate
for a real-time decision.

---

# 18. Fact / Inference Separation

Every extracted item should be classified.

FACT

Directly supported by source evidence.

INFERENCE

Derived from facts.

HYPOTHESIS

Testable proposition.

OPINION

Human or AI judgment.

PREDICTION

Forward-looking statement.

UNVERIFIED CLAIM

Insufficiently validated assertion.

Do not blend them.

---

# 19. Claim Schema

Possible fields:

claim_id

claim_text

claim_type

subject_id

predicate

object

support_status

confidence

source_ids

evidence_ids

valid_from

valid_until

as_of_time

created_at

created_by

model_id where applicable

review_status

---

# 20. Evidence Record

Possible fields:

evidence_id

claim_id

source_id

evidence_type

support_direction

source_span_reference

event_time

publication_time

retrieval_time

freshness

source_quality

independence_score

extraction_confidence

content_hash

notes

---

# 21. Support Direction

Evidence may:

SUPPORT

CONTRADICT

PARTIALLY_SUPPORT

PARTIALLY_CONTRADICT

PROVIDE_CONTEXT

BE_IRRELEVANT

The system should actively preserve contradictory evidence.

---

# 22. Contradiction Search

For important conclusions,
research should deliberately search for:

Disconfirming evidence

Alternative explanations

Negative evidence

Opposing expert analysis

Data inconsistencies

Missing assumptions

This should not be optional for high-confidence decisions.

---

# 23. Confirmation Bias Defense

Bad workflow:

Thesis:
Token X is excellent.

Search:
"Why Token X is excellent"

Preferred workflow:

Question:
"What evidence supports OR weakens Token X?"

Search separately for:

Bull case

Bear case

Structural risks

Missing evidence

Historical failures

---

# 24. Devil's Advocate Research

High-impact research may include
an independent adversarial research pass.

The adversarial researcher should ask:

What would falsify this thesis?

Which evidence has been ignored?

Which source may be biased?

Which assumptions are untested?

What information would change the conclusion?

---

# 25. Independent Research Paths

For high-impact cases,
multiple independent research paths may be useful.

Example:

Research Path A:
Primary-source focused

Research Path B:
Market-data focused

Research Path C:
Adversarial / risk focused

Do not assume multiple Agents are independent
if they share the same:

Model

Search results

Prompt

Source pool

---

# 26. Source Independence Score

Future system may estimate independence.

Potential factors:

Different publisher

Different underlying dataset

Different author

Different original event source

Different methodology

Different ownership

Repeated copies receive low independence.

---

# 27. Source Reliability Profile

Reliability may include:

Historical accuracy

Correction frequency

Primary vs secondary status

Transparency

Methodology

Conflict of interest

Update discipline

Technical quality

Past misinformation

But:

Reliability is contextual,
not permanent truth.

---

# 28. Conflict of Interest

Research should record
potential incentives when material.

Examples:

Token project publishing its own adoption claim

Exchange promoting listed asset

Influencer holding promoted token

Paid research

Venture investor discussing portfolio project

Conflict does not automatically invalidate evidence.

It changes how it should be interpreted.

---

# 29. Source Transparency

Higher-quality evidence often provides:

Methodology

Raw data

Definitions

Dates

Authors

Limitations

Correction policy

Reproducible calculations

Opaque claims deserve lower confidence.

---

# 30. Data vs Narrative Evidence

Separate:

QUANTITATIVE EVIDENCE

from

NARRATIVE EVIDENCE.

Example:

On-chain transfer:
Data.

"Whales are accumulating because they expect a bull run":
Inference.

Do not store both as equivalent facts.

---

# 31. Quantitative Verification

Numbers should be validated where practical.

Possible checks:

Unit

Currency

Time period

Calculation method

Denominator

Source

Revision status

Market definition

A percentage without denominator or period
may be misleading.

---

# 32. Deterministic Recalculation

If a published claim can be recalculated:

Recalculate it using trusted data when practical.

Example:

Reported drawdown:
72%

Independent deterministic calculation:
71.8%

This strengthens validation.

LLMs should not perform exact financial arithmetic
when code can do it reliably.

---

# 33. Unit Normalization

Normalize:

USD

BTC

Token units

Percent

Basis points

Millions

Billions

Timestamps

Different unit conventions can create silent errors.

---

# 34. Entity Resolution

Research must identify what entity is actually being discussed.

Examples:

Token ticker collisions

Rebranded projects

Wrapped tokens

Multiple chains

Company vs foundation

Exchange subsidiary vs parent

Never rely on name similarity alone.

Use canonical IDs.

---

# 35. URL Is Not Identity

A URL can change.

A page can change.

A domain can change ownership.

Important source records should use:

source_id

canonical URL

publisher

retrieval timestamp

content hash where possible

archive reference where appropriate

---

# 36. Content Hashing

Important retrieved documents may eventually receive
cryptographic content hashes.

Purpose:

Detect source changes.

Verify archived evidence.

Link predictions to exact evidence versions.

Hashing proves content identity,
not truth.

---

# 37. Source Snapshotting

High-impact research should preserve
a snapshot or durable reference when legally permitted.

Examples:

Document copy

Structured API snapshot

Archived JSON

Content hash

Timestamped source artifact

This supports reproducibility.

---

# 38. Copyright and Licensing

Research architecture must distinguish:

Read permission

Storage permission

Commercial use

Redistribution

Derived-data rights

Long-term retention

Do not assume publicly accessible content
can be freely redistributed.

---

# 39. Research Extraction

AI may extract facts from documents.

Extracted facts must retain:

source_id

source location

model_id

prompt version

extraction confidence

timestamp

AI extraction is not itself the source.

---

# 40. Exact Evidence Reference

Where systems permit,
store precise evidence location.

Examples:

Page

Section

Paragraph

Line

Timestamp in video

Table row

API record ID

Transaction hash

This improves auditability.

---

# 41. Table Extraction

Tables are high-risk for extraction errors.

Potential failures:

Wrong row

Wrong column

Merged cells

Unit mismatch

Footnotes ignored

Historical period confused

Important table values should receive
deterministic or human verification where practical.

---

# 42. PDF / Document Verification

For important reports:

Do not rely only on search snippets.

Read relevant source sections.

Inspect tables / figures if required.

Preserve page references.

Record publication version.

---

# 43. Image / Chart Evidence

Charts may be useful evidence.

But visually inferred values
should not replace underlying numeric data
when the data can be obtained directly.

Store:

chart source

date

methodology

underlying dataset if available

---

# 44. Social Evidence

Social platforms may reveal:

Narrative velocity

Community reaction

Breaking information

Rumors

Developer discussion

But risks include:

Bots

Coordinated promotion

Paid campaigns

Fake engagement

Deleted posts

Impersonation

Edited content

Social evidence requires separate reliability treatment.

---

# 45. Rumor Handling

Rumors must be labeled:

UNVERIFIED

Do not transform:

"Reports suggest..."

into:

"Fact confirmed."

Possible workflow:

Rumor discovered
    ↓
Search primary confirmation
    ↓
Search independent confirmation
    ↓
If none:
Remain UNVERIFIED

---

# 46. Breaking News Handling

During fast-moving events:

Evidence may be incomplete.

System should distinguish:

CONFIRMED

PROVISIONAL

DISPUTED

UNVERIFIED

RETRACTED

Confidence may change over time.

Preserve earlier states.

---

# 47. Retraction Handling

If source retracts information:

Do not delete historical record.

Record:

Original claim

Retraction

Retraction time

Affected predictions

Affected research

Potential reevaluation requirement

---

# 48. Correction Propagation

If material evidence changes:

Identify downstream artifacts.

Possible affected components:

Research reports

Agent conclusions

Predictions

Backtests

Evaluations

Memory

Risk assessments

Flag them for review.

---

# 49. Evidence Confidence

Evidence confidence should consider:

Source quality

Freshness

Directness

Independence

Extraction quality

Consistency

Data completeness

Methodological transparency

Do not reduce everything immediately
to one opaque number.

---

# 50. Claim Confidence

Claim confidence differs from source confidence.

Example:

Excellent source

but ambiguous statement.

Claim confidence may remain moderate.

Conversely:

Multiple independent medium-quality sources

may collectively strengthen a claim.

---

# 51. Evidence Aggregation

Avoid simple vote counting.

Bad:

3 sources support
2 sources oppose
Therefore bullish.

Preferred:

Evaluate:

Source authority

Independence

Freshness

Directness

Methodology

Contradictions

Missing information

---

# 52. Correlated Evidence

Ten sources relying on one dataset
may represent only one underlying evidence channel.

Track evidence lineage
to avoid false confidence.

---

# 53. Negative Evidence

Absence of expected evidence may matter.

Example:

Project claims major adoption.

Expected:
On-chain activity.

Observed:
No corresponding activity.

This may be useful negative evidence.

But absence must be interpreted carefully.

---

# 54. Missing Evidence

Explicitly record:

What evidence should exist?

What evidence was searched?

What was not found?

Was absence meaningful?

Never convert missing data automatically into:

False.

---

# 55. Unknown State

Valid research conclusions include:

UNKNOWN

INSUFFICIENT_EVIDENCE

CONFLICTED

UNVERIFIED

STALE_INFORMATION

Research quality improves when the system
is allowed not to know.

---

# 56. Evidence Package

Every important research task should output
an Evidence Package.

Possible structure:

research_id

objective

data_cutoff

executive_summary

validated_claims

unverified_claims

supporting_evidence

contradictory_evidence

primary_sources

secondary_sources

data_sources

source_quality

freshness

known_unknowns

conflicts

risk_flags

research_gaps

confidence

trace_id

created_at

---

# 57. Decision Package vs Evidence Package

Evidence Package:

WHAT evidence exists.

Decision Package:

WHAT the system recommends.

Keep them separate.

Research Engine should not secretly become
the decision engine.

---

# 58. Research Trace

Every serious run should eventually record:

queries

sources discovered

sources opened

sources rejected

reason rejected

tool calls

retrieval timestamps

models

prompts

extracted claims

contradictions

final evidence package

This enables debugging and evaluation.

---

# 59. Rejected Sources

Rejected sources are useful data.

Possible reasons:

Duplicate

Too old

Low authority

Irrelevant

No methodology

Unverifiable

Suspected manipulation

Prompt injection

Access failure

Keep rejection reason where useful.

---

# 60. Search Query Audit

Important research should record
query strategy when practical.

This helps determine:

Was research biased?

Was contradictory evidence searched?

Were key terms omitted?

Did search formulation influence outcome?

---

# 61. Query Diversification

One query can bias discovery.

For complex research,
use multiple query perspectives.

Example:

"Token X adoption"

"Token X risks"

"Token X exploit"

"Token X unlock schedule"

"Token X criticism"

"Token X official documentation"

---

# 62. Search Language Diversity

Important projects may have evidence
in multiple languages.

Do not assume English-only sources
capture the full information landscape.

Language expansion should be used
when relevant and evaluated for quality.

---

# 63. Research Stopping Rule

Research should stop when:

Required evidence obtained

Major contradictions addressed

Marginal information value becomes low

Budget exhausted

Time limit reached

Critical data unavailable

Human review required

Infinite research is not intelligence.

---

# 64. Marginal Evidence Value

Before another research round ask:

Will additional evidence materially change:

Confidence?

Risk?

Conclusion?

Action?

If unlikely:

Stop.

---

# 65. Research Depth

Possible modes:

FAST

STANDARD

DEEP

FORENSIC

FAST:
High-value minimum evidence.

STANDARD:
Normal research.

DEEP:
Multiple independent evidence channels.

FORENSIC:
Maximum provenance, reconstruction,
adversarial research and archival support.

Risk determines depth.

---

# 66. High-Risk Research

High-impact conclusions should require:

Primary evidence where available

Independent corroboration

Contradiction search

Source-quality review

Point-in-time verification

Evidence provenance

Human review where appropriate

---

# 67. Agent Research Permissions

Research Agents should normally receive:

READ permissions.

Research should not require:

Trading permission

Withdrawal permission

Account mutation

Production configuration changes

Least privilege applies.

---

# 68. External Content Is Untrusted

All externally retrieved content must be treated as:

UNTRUSTED DATA.

Examples:

Website text

PDF content

News

Social media

API output

MCP results

Documents

Retrieved content may contain malicious instructions.

It must not redefine system policies.

---

# 69. Prompt Injection Defense

External content such as:

"Ignore previous instructions"

"Reveal secrets"

"Execute this transaction"

must remain content,
not become trusted instructions.

Instruction hierarchy must be enforced outside
untrusted evidence.

---

# 70. Tool Output Validation

Tool results may be:

Incorrect

Malformed

Manipulated

Stale

Incomplete

Malicious

Critical results should receive:

Schema validation

Source validation

Range checks

Cross-checking where needed

---

# 71. Research Sandbox

Untrusted documents or code
should be processed in isolated environments
where appropriate.

Research processing should not automatically receive:

Secrets

Capital credentials

Production write access

Private unrelated datasets

---

# 72. Research Agent Hallucination

Common failure:

Agent produces a plausible fact
not present in evidence.

Mitigation:

Claim-to-source mapping.

Every important factual claim must have
supporting evidence references.

Unsupported claims should be marked or rejected.

---

# 73. Citation Completeness

For high-impact reports:

Important factual claims should be traceable.

Not every sentence requires separate citation,
but every material factual basis should.

A confident paragraph with no evidence
should receive reduced trust.

---

# 74. Citation Correctness

A citation is not sufficient
if the source does not actually support the claim.

Evaluation must test:

Entailment

Correct context

Date

Entity

Magnitude

Scope

Citation presence alone is not evidence quality.

---

# 75. Citation Drift

A source page may change.

Important research should preserve:

retrieval time

content version where possible

snapshot / hash

This prevents future citation mismatch.

---

# 76. Research Memory Integration

Validated research may feed Memory.

But only after:

Classification

Evidence check

Deduplication

Security review

Unverified claims should not become trusted semantic memory.

---

# 77. Prediction Ledger Integration

Research used for a prediction should link to:

prediction_id

evidence_package_id

data_cutoff

Important predictions should remain reconstructable.

---

# 78. Evaluation Engine Integration

Research Engine should itself be evaluated.

Metrics may include:

Source precision

Source recall

Primary-source rate

Citation correctness

Citation completeness

Contradiction detection

Fact extraction accuracy

Unsupported-claim rate

Freshness

Latency

Cost

Research usefulness

---

# 79. Research Golden Set

Maintain evaluated research scenarios.

Examples:

Historical exchange collapse

Token unlock event

Fake rumor

Protocol exploit

Bull narrative

Manipulated social campaign

Conflicting official statements

Outdated documentation

Ticker collision

Retracted article

Use these for regression tests.

---

# 80. Adversarial Research Evaluation

Test the system using:

Fake sources

Misleading pages

Prompt injection

Copied misinformation

Manipulated statistics

Incorrect timestamps

Outdated pages

Ticker ambiguity

Contradictory sources

The system should degrade safely.

---

# 81. Retrieval Evaluation

Measure:

Did search find the right evidence?

Did it miss primary sources?

Did it over-retrieve noise?

Did it retrieve stale information?

Did it find contradictory evidence?

Retrieval quality must be measured independently
from model reasoning.

---

# 82. Extraction Evaluation

Measure:

Entity correctness

Number correctness

Date correctness

Unit correctness

Claim classification

Evidence-span accuracy

Table extraction accuracy

Do not assume strong reasoning implies strong extraction.

---

# 83. Synthesis Evaluation

Evaluate whether synthesis:

Represents evidence fairly

Preserves contradictions

Distinguishes fact from inference

Reflects source quality

Avoids overconfidence

Includes major unknowns

Does not invent missing evidence

---

# 84. Research Model Routing

Different research stages may use different models.

Example:

Discovery:
Fast model

Document extraction:
Reliable structured-output model

Deep synthesis:
Strong reasoning model

Adversarial review:
Independent model family

Router should select based on evaluation,
not brand preference.

---

# 85. Reranking

Research systems may use rerankers
to prioritize retrieved evidence.

Reranking should consider:

Relevance

Freshness

Authority

Independence

Task fit

Reranking models themselves require evaluation.

---

# 86. Retrieval-Augmented Generation

RAG may be useful.

But RAG is not automatically reliable.

Failure modes:

Wrong retrieval

Missing source

Stale source

Poor chunking

Context overload

Bad reranking

Hallucinated synthesis

RAG quality must be evaluated end to end.

---

# 87. Chunking

Document segmentation may affect retrieval.

Possible factors:

Section boundaries

Paragraph boundaries

Tables

Headings

Semantic units

Do not choose one chunk size
as permanent truth.

Evaluate it.

---

# 88. Context Budget

Agents should receive:

High-signal evidence

not:

Every retrieved document.

Prefer:

Relevant source fragments

Structured facts

References to full artifacts

This reduces noise and token cost.

---

# 89. Evidence Compression

Long evidence collections may be compressed.

Compression must preserve:

Claim

Supporting evidence

Contradictions

Source IDs

Dates

Uncertainty

Original sources remain authoritative.

---

# 90. Research Artifacts

Possible durable artifacts:

Evidence Package

Source Table

Claim Table

Contradiction Report

Research Trace

Risk Notes

Document Snapshot

Structured Dataset

Each artifact receives:

artifact_id

version

timestamp

provenance

---

# 91. Research Versioning

Research methodology should be versioned.

Examples:

research_policy_v0.1

source_scoring_v0.2

contradiction_policy_v0.3

citation_policy_v1.0

Historical predictions should preserve
which research policy was used.

---

# 92. Reproducibility

A serious research result should eventually record enough information
to reconstruct it approximately.

Record:

Research objective

Time cutoff

Queries

Source IDs

Snapshots

Models

Agent versions

Prompt versions

Tool versions

Extraction versions

Final evidence package

---

# 93. Research Cost

Track:

Search cost

Model cost

Data-provider cost

Compute cost

Time

Human review

Best research is not:

Maximum number of sources.

It is:

Sufficient reliable evidence
at appropriate cost and latency.

---

# 94. Source Diversity vs Source Quantity

Twenty low-quality sources
may be worse than:

One primary source

One independent data source

One strong adversarial analysis

Optimize evidence quality,
not source count.

---

# 95. Research Failure Modes

Possible classes:

SOURCE_NOT_FOUND

SOURCE_UNAVAILABLE

SOURCE_STALE

SOURCE_CONFLICT

ENTITY_AMBIGUITY

DATA_MISMATCH

EXTRACTION_FAILURE

CITATION_FAILURE

PROMPT_INJECTION

RETRIEVAL_FAILURE

INSUFFICIENT_EVIDENCE

TOOL_FAILURE

RESEARCH_TIMEOUT

Failures must be visible.

---

# 96. Graceful Degradation

If required evidence is unavailable:

Do not fabricate.

Example:

On-chain source unavailable.

Output:

ONCHAIN_EVIDENCE_UNAVAILABLE

Confidence reduced.

Research may continue
only if remaining evidence is sufficient.

---

# 97. Research Confidence

Final confidence should consider:

Evidence quantity

Evidence quality

Independence

Freshness

Contradiction level

Missing information

Extraction reliability

Data quality

Confidence should not reflect writing style.

---

# 98. No False Precision

If evidence is weak:

Do not return:

83.7% confidence

merely because the system can generate a number.

Confidence precision must be justified
by calibration and methodology.

---

# 99. Human Review

Human review may be required for:

Critical capital decisions

Major source conflict

Security claims

Legal / regulatory interpretation

Ambiguous project identity

Major allegations

Insufficient provenance

High uncertainty

Human review does not replace evidence requirements.

---

# 100. Long-Term Evidence Moat

Over time the system may accumulate:

Validated source reliability

Claim histories

Research failures

Contradiction patterns

Model research performance

Human research corrections

Historical evidence packages

Point-in-time source archives

This becomes institutional research intelligence.

---

# 101. What We Own

Crypto Intelligence OS should aim to own:

Research methodology

Evidence schemas

Claim history

Evaluation history

Research traces

Source reliability profiles

Derived intelligence

Failure history

Historical decision context

Third-party source content remains subject
to its own rights and licenses.

---

# 102. Production Readiness Gate

Before Research & Evidence Engine becomes production-grade:

Source registry implemented

Entity resolution validated

Timestamp policy implemented

Point-in-time controls tested

Claim schema validated

Evidence schema validated

Source lineage operational

Contradiction search operational

Citation correctness evaluated

Freshness policy operational

Prompt-injection defenses tested

Tool outputs validated

Source snapshot policy defined

Licensing review implemented

Research traces operational

Evaluation suite passed

Failure handling tested

Memory integration tested

Prediction Ledger integration tested

No critical unresolved issues

---

# Final Doctrine

SEARCH IS NOT TRUTH.

A SUMMARY IS NOT A SOURCE.

A CITATION IS NOT VALID UNLESS IT SUPPORTS THE CLAIM.

REPETITION IS NOT INDEPENDENT CONFIRMATION.

POPULARITY IS NOT EVIDENCE.

AI CONFIDENCE IS NOT PROOF.

PRIMARY DATA SHOULD WIN WHEN APPROPRIATE.

CONTRADICTORY EVIDENCE MUST SURVIVE SYNTHESIS.

UNKNOWN IS A VALID RESULT.

---

# Final Principle

CRYPTO INTELLIGENCE OS MUST NEVER ASK ONLY:

"WHAT DOES THE INTERNET SAY?"

IT MUST ASK:

"WHAT CAN BE SUPPORTED BY TRACEABLE,
TIME-CORRECT,
INDEPENDENT,
HIGH-QUALITY EVIDENCE?"

CONFIDENTIAL — CRYPTO INTELLIGENCE OS
