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
2. **TOOL CHECK — proactive, not user-prompted:** Choose the most capable
   *available* tool for the task: deterministic code for data/statistics;
   Codex for complex implementation or code review **when actually accessible**;
   specialist research and adversarial agents for bounded, independently
   reviewable hypotheses. Reuse installed tools/workflows before adding agents,
   providers, models, frameworks, or dependencies. If Codex/agents are
   inaccessible, state that clearly and perform the available part; never
   claim they ran or make the user rediscover the tool strategy.
3. **RED SIGN — STOP:** Stage-6 scientific NO-GO; Issue #81 A1–A6 source
   vintage, immutable custody, real runner isolation and independent signoff
   remain unverified. No approval for new real-data fitting, protected OOS,
   paid providers, trading, unbounded dispatch, or Freeze. Historical V3
   result stays 0/24 freeze-ready; passing CI cannot change it.
4. **YELLOW SIGN — ENGINEERING ONLY:** Offline synthetic tests, safe read-only
   audits, bounded metadata checks, and draft code/reviews may proceed.
   Record which claims are *self-reported* versus externally witnessed.
   Missing scheduled origins, issuance-to-target elapsed lead, source first
   availability, and late/near-expiry forecasts remain visible; never
   backfill, cherry-pick, or relabel elapsed lead as nominal horizon.
5. **GREEN SIGN — ONLY AFTER INDEPENDENT GATES:** Verify lawful source rights,
   A1–A6, price/outcome-blind eligibility, effective-N/power, a fixed
   preregistered hypothesis and cost ceiling. Only then request separately
   authorized real fitting and an untouched, dependence-aware comparison
   against persistence. An independent reviewer—not an agent vote—decides
   readiness. No automatic production promotion.
6. **SCALING SIGN:** First measure quality gain versus persistence, stability,
   coverage, reviewer-found defects, compute time, provider tokens and actual
   cost. Increase agents, model families or timeframes only if a distinct
   hypothesis or measurable marginal value justifies them. The requested
   13-horizon program in Issue #78 is a target, not 13 validated systems.
7. **SECURITY SIGN:** The repository is currently **public**; no branch is
   private inside it. Do not add secrets, licensed nonpublic datasets,
   private attestations, protected paths or proprietary artifacts here.
   Escalate repository visibility/IP decisions to the owner.
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

- Stage-6 remains **scientific NO-GO / NO_FREEZE** until independently verified evidence changes that decision.
- Do not read or tune against Fresh Locked OOS or V2 Locked OOS. Do not use unauthenticated historical availability claims, rewrite frozen inference, or select hypotheses based on observed outcomes.
- Do not fit real-data models, run paid providers, change repository visibility, merge PRs, initiate trades, or start recurring workflows without explicit authorization and necessary approvals.
- A green CI or synthetic-only software GO is **not** forecasting accuracy, data provenance, power, privacy, or financial performance evidence.
