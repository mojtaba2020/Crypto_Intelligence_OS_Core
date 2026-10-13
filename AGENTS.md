# Coding-agent instructions

**Goal: the smallest correct, reviewable result.** Brevity must not hide risk.

- Answer a question directly. Do not edit code or create an agent, script, PR, or document unless the task actually needs one.
- Before implementing, check whether an existing function or configuration already solves it. Read only relevant files; avoid blanket repo exploration for small changes.
- Prefer one focused change over a new abstraction, framework, dependency, agent, or speculative feature. Do not refactor unrelated code.
- For simple work, skip long plans and repetitive progress narration. Ask a question only when a missing fact blocks safe execution.
- Make the minimal safe diff, not the fewest lines at any cost. Preserve contracts, backwards compatibility, security, and reproducibility.
- Test the changed behavior and likely failure modes; run required quality gates. Report only tests actually run. Never weaken tests to obtain green CI.
- Final response: normally **three short parts** — what changed, evidence/tests, remaining blocker or next action. Avoid praise, promises, repeated explanations, and inflated results.
- If blocked, state the exact missing input/permission and stop. Do not simulate an executed action or an independent reviewer.

## Bitcoin research safety boundaries

- Stage-6 remains **scientific NO-GO / NO_FREEZE** until independently verified evidence changes that decision.
- Do not read or tune against Fresh Locked OOS or V2 Locked OOS. Do not use unauthenticated historical availability claims, rewrite frozen inference, or select hypotheses based on observed outcomes.
- Do not fit real-data models, run paid providers, change repository visibility, merge PRs, initiate trades, or start recurring workflows without explicit authorization and necessary approvals.
- A green CI or synthetic-only software GO is **not** forecasting accuracy, data provenance, power, privacy, or financial performance evidence.
