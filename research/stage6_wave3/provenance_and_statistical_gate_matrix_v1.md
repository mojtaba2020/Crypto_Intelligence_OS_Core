# Stage-6 provenance and preregistration approval gates (design only)

**Document version:** V1 · **Status:** UNVERIFIED / NO_RUN / NO_FREEZE

This is an auditable checklist, **not evidence that any checks have actually
passed**. No actual market feed, source manifest, mount configuration, reserved
data or forecast outcomes were consulted when preparing it. Keep the Stage-6
scientific disposition **NO-GO (0/24 Freeze-ready)**. Draft PRs #73/#77 are not
authorized for training or deployment. No paid APIs or recurring work.

## A. Who must supply and verify each evidence item?

Two different human-controlled roles are required for approval: an evidence
producer with legitimate source/deployment access, and an independent reviewer
who did not create or modify the source/manifest. A code-level feature unit test
cannot act as either role. Record reviewer identity and time in an immutable
operator-controlled record. Never paste credentials, raw locked prices, private
paths or secrets in a public Issue.

| Gate | Producer must supply | Reviewer must independently verify | Default decision |
| --- | --- | --- | --- |
| A1: data-source identity | Exchange, instrument, quote/base unit, vendor, collection process, API/source revision, canonical bar convention, extraction time and coverage with development-only classification | Documentary lineage back to authenticated source and external SHA-256; no invented publication claims | UNVERIFIED |
| A2: provenance & revisions | Immutable source-audit object with extraction cutoff; per-bar first-observed, last-revised and finalization times, gaps and changed-record log | Every feature and label was available **as actually published** by its origin, not merely by candle-close clock; access excludes all reserved outcomes | UNVERIFIED |
| A3: immutable approval | Separate review signoff and pinned byte digest for dataset + source audit + manifest **outside job-writable roots** | Job cannot replace its own approval, approve an arbitrary self-attested hash, or revise original inputs; approval applies to exact source, periods, code and access scope | UNVERIFIED |
| A4: operating-system isolation | Read-only input and manifest mounts, write-only intended output, approved absolute roots, immutable path ancestors, file descriptor / mount authority evidence | With the **real runner identity**, deny writing inputs/manifests, deny reading reserved paths and all bind/hardlink/symlink aliases, prevent mount swaps/rename races and helper bypass | UNVERIFIED |
| A5: reproducible executable | Immutable container/image digest, Python/CatBoost and transitive dependency pins, source tree/entrypoint digest, network policy, CPU and process limits | Executed loaded code and dependencies match approved identities; guarded CLI is sole authorized run path; no unexpected provider credentials/network targets | UNVERIFIED |
| A6: approval & stop conditions | Reviewer-signed evidence manifest; scope, prospective timestamp windows, safe return and abort policy | Every preceding gate is PASS from independently inspectable artifacts; no contradictions; false/missing evidence fails closed | NO_RUN |

**Important:** lexical root separation, SHA hashes of caller-supplied bytes,
\`is_complete\`, \`source_bars\` and \`source_finalized_at\` assertions by
themselves **never** establish the above gates. A read-only sandbox lacking
actual audit evidence must stay UNVERIFIED, not PASS.

### Synthetic adversarial authorization checks (not yet executed)

1. An input/manifest root that is a parent or descendant of an output root is rejected.
2. Equal roots and symlinked ancestor or file paths are rejected.
3. A hardlink or bind-mounted alias cannot defeat OS-enforced read-only policy.
4. An attempted write to the approved input or manifest fails under runner credentials.
5. A reserved-data sentinel and every known alias are unreachable to runner identity.
6. Parent replacement and mount substitution races cannot redirect reads/writes.
7. An unapproved, replaced or mismatched source manifest is rejected.
8. First-publication and post-publication revisions later than forecast availability exclude the affected origin; no backfill to make it pass.
9. A helper/internal Python entrypoint cannot bypass the authorized CLI isolation.
10. A modified executable, feature import, dependency or container digest is rejected.

These are **proposed future acceptance tests**. Do not describe them as run
until an independent authorized operator provides verifiable results.

## B. Label-blind calendar feasibility review (future, separately authorized)

- Authorized input is *only* independently approved non-outcome timestamp
  metadata (exchange, source family, origin-open, forecast availability, target
  maturity, allowed/excluded windows, gap/revision flags, schedule IDs). Never
  see price/volume outcomes or hidden/locked slices for feasibility selection.
- Preserve all predeclared scheduled origin timestamps, including rejected
  timestamps, rejection reasons and non-observed outcomes; do not replace bad
  origins or compress calendar time.
- Source timestamps and source-report publication latency must be audited
  independently; otherwise every availability-dependent eligibility remains
  unknown.
- Calculate the number of *eligible scheduled* origins only after fixing the
  prospective cadence/embargo. An eligible count is **not** an independent
  effective sample size. Correlation, serial dependence and a power-adequate
  independent N remain separate requirements.
- If data boundaries overlap historic judge/locked-OOS windows, or the
  timestamp-only review cannot be performed without inspecting outcomes, abort
  the review with **NO_RUN**; don't search for alternative good-looking windows.

## C. Unresolved alternative experimental proposals (no performance selection)

**Alternative S** (STATS-03): daily one-bar forecast, new 29-bar feature-history
contract, fixed four-feature short-history CatBoost, zero-return persistence
baseline, paired squared log-return-error inference; alpha familywise 0.05.
Feature-history change requires *new audited implementation and eligibility*.

**Alternative F** (FEATURE-03): daily seven-bar forecast, retain existing
365-bar history gate, fixed existing features versus those same features plus
the one proposed volume-supported reversal scalar; descriptive synthetic-only
preflight exists. Requested 24 fits **exceed** current opt-in 12-fit cap.

These proposals are mutually **unselected**. A future preregistration must
designate **at most one** independently justified research question before any
new outcomes are seen, or explicitly declare **NO_RUN**. Do not use historical
performance, observed p-values, model convenience or number of agent votes to
choose a winner.

### Prospective registration fields — all required before a confirmatory run

| Field | Required decision/evidence | Current status |
| --- | --- | --- |
| Primary hypothesis and complete candidate family | Exact feature mask, model and parameters, familywise multiplicity handling, alternative cancellation/competing hypothesis rule | TBD |
| Source and identity | Independently reviewed exchange/pair, source intervals, extraction SHA and manifest SHA, reviewer identities, prohibited-window list | UNVERIFIED |
| Calendar windows | UTC train / selection / diagnostic / true prospective-evaluation boundaries, fixed anchor and cadence, no leakage | TBD |
| Availability and maturity | Bar-close **plus actual publication/revision** time; mature-label purge and preregistered embargo; gap exclusions retained | UNVERIFIED |
| Metrics | Fixed training objective, squared log-return paired primary inference, zero-return persistence baseline; APE descriptive only | Proposed, not frozen |
| Effective N and power | Economically justified positive minimum effect, audited paired-loss variance and dependence model, alpha 0.05, power at least 0.80; independent effective-N threshold | UNVERIFIED |
| Fixed inference | Exact statistic, correlation-robust method, multiplicity adjustment, one final analysis, stopping/abort rules | TBD |
| Compute approval | Pinned hardware and max CPU/wall/RAM, maximum fits/trees and budget approved *before* use; no split invocations to evade 12-fit cap | ZERO NEW TRAINING AUTHORIZED |
| External review and permissions | Independent scientific review with signed output and explicit separate authority | NOT APPROVED |

**Fail-closed decision:** any missing preregistration identity, source trust,
power, inference, immutable isolation or sufficient untouched prospective
observations = **NO_RUN / NO_FREEZE**. A future statistical pass alone still
does not grant production or Stage-7 Freeze.

## D. Engineering signoff for isolated FEATURE-03 preflight

Draft PR #77 adds *only* a pure synthetic formula, synthetic regression tests
and design documents. Existing runner/judge paths must never import this feature
until a new separately audited protocol and explicit authorization exist.
CI passing is a software regression signal, not evidence that this feature
predicts future price movement or improves on persistence.
