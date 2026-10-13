# AI-first expert / critic / evidence workflow (proposal v1)

**DRAFT — local metadata only — zero provider calls — no autonomous workers — NO_RUN / NO_FREEZE.**

This is a small extension of the existing eight-role V3 design and 100-slot
`agent_fleet.py` dry-run planner. It **does not create more agents** or
replace the existing Stage-6 scientific and security gate.

## For one significant decision

1. **Proponent:** define one specific, falsifiable claim, exact Git commit and
   testable evidence references. Use the smallest change.
2. **Independent critic role:** on that same pinned commit, explicitly search
   for counterexamples, leakage, data-provenance gaps, unsafe permissions,
   statistical selection bias and unintended cost. Record counterevidence
   and unresolved blockers. A separate role label or identifier alone does
   **not** prove independent execution, human identity or independent access.
3. **Deterministic tests:** publish reproducible commands, logs and failures
   from the exact same commit. A self-reported pass is not verification.
4. **Gate:** run the *pure, offline* `assess_review_packet` checker on those
   metadata claims. Any critic blocker, missing reference, stale code SHA,
   failed test or same proponent/critic identifier => BLOCKED. A complete
   packet is only **ready for external verification**; it is NEVER an
   authorization to deploy, fit, spend, trade or Freeze.
5. **Independent human/operator attestation** remains mandatory wherever
   evidence custody, real deployment security, regulated action or Stage-6
   promotion requires it. If no valid independent evidence exists, STOP.

## Benchmark quality rather than claim universal superiority

For comparable, pinned tasks compare before/after: user-visible result,
number and severity of bugs, relevant tests passing, reviewer-found defects,
source integrity, wall-clock duration, provider tokens (when actually measured)
and itemized dollars (when actually billed). Disclose unknown values; do not
invent a percentage saving or pretend that a fast, small diff is safer.
Model/reviewer changes require fresh independent evaluation.

## Stage-6 current hard blockers

Historical first-observed/source-revision information and independently
controlled original data bytes are unverified (Issue #81 A1–A6). Existing
frozen V3 research has **0/24 Freeze-ready** (Issue #71). Green CI from this
PR is a software check only. No new market retrieval, paid LLM, locked OOS,
external attestations, autonomous scheduling, CI permission widening or
deployment is performed by this proposal.

This policy is advice and packet validation, not a cryptographic signature,
workload identity, external attestation, active AI-orchestration or proof that
an AI outperforms a human specialist.
