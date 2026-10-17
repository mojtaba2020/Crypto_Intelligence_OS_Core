# Coding-agent instructions

**Goal: the smallest correct, reviewable result.** Brevity must not hide risk.

- Answer a question directly. Do not edit code or create an agent, script, PR, or document unless the task actually needs one.
- Before writing code, use the decision ladder: is a change needed? -> reuse existing code -> standard library -> native platform -> installed dependency -> smallest correct new code. Stop at the first safe solution. Read only relevant files.
- Prefer one focused change over a new abstraction, framework, dependency, agent, or speculative feature. Do not refactor unrelated code.
- For simple work, skip long plans and repetitive progress narration. Ask a question only when a missing fact blocks safe execution.
- Make the minimal safe diff, not the fewest lines at any cost. Preserve contracts, backwards compatibility, security, and reproducibility.
- Test the changed behavior and likely failure modes; run required quality gates. Report only tests actually run. Never weaken tests to obtain green CI.
- Final response: normally **three short parts** — what changed, evidence/tests, remaining blocker or next action. Avoid praise, promises, repeated explanations, and inflated results.
- If blocked, state the exact missing input/permission and stop. Do not simulate an executed action or an independent reviewer.

## Project navigation signs — check before substantial work

**NORTH STAR — measurable Bitcoin forecasting research, not activity for its own sake.**
The aim is trustworthy, reproducible prospective *price and direction*
evaluation across the declared horizons, with cost and information security
controlled. No promise of 90% accuracy, returns, or a business outcome.

1. **ROUTE CHECK:** Before acting, name the concrete blocker/objective, its
   existing issue/PR, required evidence, smallest deliverable, stop condition,
   and cost/API/schedule effect. If it does not move a real blocker or protect
   evidence, park it; do not create another PR merely to show progress.
2. **TOOL CHECK — planning is proactive; dispatch is not:** Identify the
   best available tool without waiting for a user to name it: deterministic
   code, Codex for complex review/implementation, or a bounded specialist
   critic when justified. Reuse what exists first. This is a *recommendation*,
   NOT permission to invoke external models, delegate to sub-agents, send
   prompts/data outside the approved boundary, or incur cost. Require explicit
   scoped human authorization for each external/sub-agent dispatch, its data
   access, provider, cost ceiling and stop rule. Otherwise do safe local work,
   describe the blocker, and do not claim an agent ran.
3. **RED SIGN — STOP:** Stage-6 scientific **NO-GO / NO_RUN / NO_FREEZE**;
   Issue #81 A1–A6 source vintages, independent immutable custody, runner
   isolation and signoff remain unverified. No Stage-6 real-data execution
   (fetch, train, backtest, score, free or paid provider, bounded or unbounded
   model/agent dispatch), protected OOS, trade or Freeze. Historical V3 stays
   0/24 freeze-ready; passing CI cannot change it.
4. **YELLOW SIGN — ENGINEERING ONLY:** Offline synthetic tests, safe read-only
   audits, bounded metadata checks, and draft code/reviews may proceed.
   Record which claims are *self-reported* versus externally witnessed.
   Missing scheduled origins, issuance-to-target elapsed lead, source first
   availability, and late/near-expiry forecasts remain visible; never
   backfill, cherry-pick, or relabel elapsed lead as nominal horizon.
5. **GREEN SIGN — ONLY AFTER INDEPENDENT GATES:** Require separated,
   independently controlled roles: source/operator, external immutable data
   custodian, restricted OS runner identity/admin, and independent reviewer /
   approver. No actor can both alter evidence/runner inputs and approve them;
   reviewer must not share the producer's writable custody or execution
   privileges. Independently verify lawful rights, A1–A6, outcome-blind
   eligibility, effective-N/power, preregistered hypothesis and cost ceiling.
   Only a separately recorded and verified gate decision can change NO_RUN;
   then require **separate explicit authorization for the exact real-data run**.
   An agent vote or PR checkbox never approves fitting, Freeze or promotion.
6. **SCALING SIGN:** First measure quality gain versus persistence, stability,
   coverage, reviewer-found defects, compute time, provider tokens and actual
   cost. Increase agents, model families or timeframes only if a distinct
   hypothesis or measurable marginal value justifies them. The requested
   13-horizon program in Issue #78 is a target, not 13 validated systems.
7. **SECURITY SIGN:** The repository is currently **public**; no branch is
   private inside it. Never commit **or transmit** secrets, licensed nonpublic
   data, private attestations, sensitive paths or proprietary artifacts to
   public issues/PRs, prompts, third-party agents/providers, logs, or uploaded
   outputs. Treat confidentiality markings as real even on public files.
   Redact first; require explicit owner approval before any external disclosure
   or sharing with an AI provider. Escalate repository visibility/IP choices.
8. **CHECKPOINT SIGN:** On completion, report: objective -> actual changes
   (links and exact commit) -> tests and independent review status -> remaining
   scientific gates -> *one highest-value next step*. No silent merges,
   recurring tasks, model dispatches or costs.

**Stage-6 route:** Issue #81 provenance/isolation -> Issue #78 fixed horizon
definitions -> approved label-blind calendar/coverage and power -> preregistered
bounded experiment -> independently reviewed outcome evidence -> possible
Freeze decision. Existing draft PRs must be inspected before opening new ones.
A detour is allowed only when it directly removes a blocker or critical risk.

## Bitcoin research safety boundaries

- Stage-6 remains **scientific NO-GO / NO_RUN / NO_FREEZE** until a separately recorded, independently verified gate decision and new scoped run authorization. Neither a PR checklist nor an agent can change this.
- Do not read or tune against Fresh Locked OOS or V2 Locked OOS. Do not use unauthenticated historical availability claims, rewrite frozen inference, or select hypotheses based on observed outcomes.
- Do not perform Stage-6 real-data runs of any kind (including free providers, fitting, scoring or bounded agent dispatch), change repository visibility, merge PRs, initiate trades, or start recurring workflows without the required independent gates and explicit scoped authorization.
- A green CI or synthetic-only software GO is **not** forecasting accuracy, data provenance, power, privacy, or financial performance evidence.
