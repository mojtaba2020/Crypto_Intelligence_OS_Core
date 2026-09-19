# CEO Control Tower — Product Decision and Delivery Contract v0.1

**Status:** approved product direction; implementation staged. **Date:** 2026-09-19. **Owner:** founder/CEO. **Privacy:** internal confidential.

## Mission

Crypto Intelligence OS is an AI-first intelligence company, not just a price dashboard or a collection of autonomous bots. The founder has a visible, auditable **CEO Control Tower** where they can issue bounded research missions, see genuine agent/task activity, inspect evidence and outputs, set budgets, pause work, and approve or reject impactful actions.

**Product objective:** deliver measurable, trustworthy research value to paying customers. A billion-dollar company is an ambition, not a forecast or promised outcome. Prove a narrow paid use case before expanding an agent organization.

## Honest current state

- Stable Core, point-in-time market data contracts and read-only Coinbase BTC/USD ingestion are implemented.
- A live public BTC/USD smoke test and 90-final-daily-bar validation have passed in GitHub Actions.
- The 90-day sample is a temporary GitHub Actions artifact, **not** a durable database.
- The current GitHub Actions jobs are deterministic Python workflows, **not** deployed autonomous LLM agents.
- No authenticated customer-facing CEO dashboard, live orchestrator, funded trading, billing, or deployed specialist-agent fleet exists yet.
- A configured agent is not running merely because its name is shown in an interface.

## CEO operating model

Founder/CEO: defines mission, success criteria, priorities, permitted scope, risk limits, weekly budget, and final review. Chief Intelligence Orchestrator: breaks approved missions into tasks and assigns the **minimum necessary** specialized workers. Workers provide structured, cited outputs; automated evaluators independently check correctness. The CEO may pause/resume/cancel *only actual supported workflows*; dangerous actions require explicit approval and are disabled in the research MVP.

## CEO Control Tower — visual specification

1. **Mission Board:** mission name, owner, objective, current stage, data cutoff, start time, last heartbeat, deadline, dependencies, failed checks, produced artifacts.
2. **Agent Floor:** actual agent ID, agent/model/prompt version, capability and allowed tools, RUNNING/IDLE/WAITING_FOR_APPROVAL/FAILED/PAUSED/NOT_DEPLOYED states. Never show fictional active workers, fake thinking, synthetic progress, or inferred heartbeats.
3. **Live Task Trace:** time-stamped steps, input snapshot ID, tool request and result, source citations, output hash, measured latency and cost (explicit UNKNOWN when unavailable), errors and retries.
4. **CEO Desk:** create bounded research mission; inspect and compare outputs; approve/reject escalations; edit mission priority and budgets; pause/cancel with backend confirmation. No inert or decorative controls. Show whether an action has actually succeeded.
5. **Evidence & Decision Lab:** Human versus independently generated AI forecasts, hybrid forecast generated only after both are locked; outcome evaluation, point-in-time correctness and versioned calibration.
6. **Company Dashboard:** validated customer value, repeat usage, conversion/revenue when observed, burn and spend ceilings, incident rate, research accuracy and data coverage. Never present fabricated traction or projected billion-dollar valuation as fact.

## Permission and operational policies

- Read-only public market data by default. No trading, transfers, withdrawals, exchange credentials or irreversible external actions in initial versions.
- Per-agent allowlisted tools, data scopes, latency limits, retry and token/dollar budgets; separate immutable risk constraints.
- Any future capital-impacting action requires specific human approval tied to task ID, scope, amount, destination and expiration; approval cannot be inferred from a chat message.
- Explicit NOT_DEPLOYED/UNKNOWN values; no agent is marked RUNNING without a real execution record and recent heartbeat.
- Append-only audit event ledger with server timestamp and actor; durable database for tasks, checkpoints, outputs and approvals, not LLM conversational memory.
- Protect the internal dashboard using authenticated access and least privilege; do not publish private research through GitHub Pages or a public demo endpoint.
- Independent evaluation and adversarial review for material conclusions. No promised returns.

## First three real operational roles (not three pretend LLM employees)

| Role | First executable scope | Current status as of this decision |
|---|---|---|
| Data Collector | Read-only BTC/USD retrieval and archival workflow | Deterministic GitHub Actions job implemented; not an autonomous LLM agent |
| Data Quality Worker | Verify timestamps, completeness, source, sequence and integrity; publish evidence | Validation logic exists inside workflows; independent agent service NOT_DEPLOYED |
| Cycle Research Agent | Evaluate versioned halving/cycle hypotheses with point-in-time backtests and counterevidence | NOT_DEPLOYED; requires durable market database and backtesting engine |

## Delivery sequence and acceptance criteria

### Gate A — durable data (next)
Implement a real persistent store for public BTC/USD history, raw-source provenance, revisions and ingestion timestamps; backfill sufficient verified coverage, reconcile missing candles, make archival artifacts recoverable. CI and one real live ingestion must pass.

### Gate B — genuine control-plane telemetry
Instrument the existing deterministic collector and data-quality validator as distinguishable worker **runs**. Persist task/run states, start/end/heartbeat, bounded mission parameters, tool results, source IDs, quality checks, failure and retry events. Build tests for invalid transitions, idempotent retries, cancellation, permission boundaries and append-only audit behavior.

### Gate C — visible CEO MVP
Build an authenticated, responsive web-based Control Tower (iPad-friendly / installable PWA later). Display actual task/run state, source-backed historical logs and archived outputs. Start/pause/cancel control only where backend supports them and confirms transitions. Explicitly show NOT_DEPLOYED for future agents.

### Gate D — independently evaluated intelligence
Implement Cycle Research Agent and independent AI research path. Create immutable pre-outcome forecast ledger, deterministic baseline, backtesting with no look-ahead, out-of-sample and walk-forward evaluations. Then introduce Hybrid and calibrated weights if evidence supports them.

### Gate E — customer validation
Interview a narrowly defined researcher persona, measure repeated use and paid demand; iterate on verified customer outcomes before scaling infrastructure, agents, subscription tiers or hiring.

## Architectural decision

**One private, provider-neutral intelligence engine + authenticated CEO Control Tower + machine-readable API/agent tools.** Website, PWA, chat and external assistant are alternative interfaces to the same engine, not separate implementations. Prioritize reliable underlying capabilities over visually busy dashboards or large agent counts.

## Non-goals for this release

No 100-agent simulation, fake corporate staff, agent-generated trading orders, unauthenticated public dashboard, bank/exchange connection, fabricated live monitoring, unsupported valuation claims, or indefinite background operation without an explicit scheduler.
