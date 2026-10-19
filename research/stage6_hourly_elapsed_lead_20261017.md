# Stage-6: hourly nominal horizon versus elapsed prospective lead

**DRAFT / OFFLINE / METADATA CLAIMS ONLY / NO_RUN / NO_FREEZE.** The repository is
public. This change does not read BTC prices, outcomes, ledgers, restricted
inputs, provider responses, credentials, historical research windows, or live
GitHub/market APIs. It does not alter any scheduled workflow or train models.

## Why this exists

The existing `main` hourly producer uses the **opening** of its last completed
hourly bar as `origin_hour_utc`. Under its bar-close convention, target close
is `origin_hour_utc + (horizon_hours + 1) * 3600`. It may issue its prediction
anytime during the next hour after source-bar completion. Consequently, a
nominal **1h** forecast may have less than 60 minutes of elapsed lead, including
near-expiry claims, and cannot be described unconditionally as 60 minutes ahead.
This is independent of prediction accuracy, source first-availability, or the
already identified pre-fit timestamp flaw addressed in unmerged PR #89.

## Bounded offline audit

`audit_elapsed_lead(plan, records)` in
`scripts/stage6_hourly_elapsed_lead_audit.py` accepts only an exact,
price-free, integer-UTC-seconds schema for one **fixed** 1–168 hour schedule
and the fixed `(1, 4, 12, 24)` bar-horizon family. The caller must explicitly
provide `plan.claim_semantics = "bar_aligned"` or `"minimum_elapsed"`; an omitted or
unknown choice **fails closed**. Never select claim semantics retrospectively
based on market outcomes. Each record identifies a
claimed scheduled GitHub run, completed-bar origin, horizon, local issue
instant, claimed GitHub log observation, and target close. It:

- Enumerates **every** scheduled `(origin, horizon)` including absent claims.
- Rejects noncanonical horizons, duplicates, target-close inconsistencies,
  cross-origin run-ID reuse, cross-run origin replenishment, prices and outcomes.
- For a claimed run/origin, **all issued timestamps must agree** with the deployed
  four-horizon producer's single issuance clock. Contradiction marks **all
  received slots** in that batch `INCONSISTENT_BATCH_ISSUANCE_CLAIMS`, omitting
  their elapsed leads even when each timestamp alone appears pre-close. It is
  not a trusted proof of common issuance, only a negative consistency check.
- Retains invalid, immature or late claims **as blocked/unknown categories**,
  never silently discards them from scheduled denominators.
- For explicitly predeclared `minimum_elapsed` claims, checks `target_close -
  claimed_publication_upper_bound_utc >= horizon_hours * 3600`. Even a one-second
  shortfall produces `INSUFFICIENT_CLAIMED_ELAPSED_HORIZON`, top-level `BLOCKED`,
  and a separate `short_elapsed_horizon_count`; the *actual claimed lead* is
  retained diagnostically but not counted among full-horizon claims. This
  detects the P1 full-elapsed-horizon labeling flaw; it cannot repair the
  current live producer's target alignment or prove a caller-supplied timestamp.
- For `bar_aligned` claims, retains observed variable elapsed leads including
  near-expiry pre-close claims, but **never** calls them a full elapsed horizon
  or issues scientific PASS. The two definitions are distinct estimands.
- Sets top-level `status=BLOCKED` if **any** scheduled slot is missing or
  any claim is late, unknown or inconsistent. Even if all claims are present
  and internally ordered, status stays `UNVERIFIED_ELAPSED_LEAD_METADATA_ONLY`,
  never `PASS`; neither state authorizes scientific runs.
- Computes `target_close - claimed_publication_upper_bound_utc` **only** for
  internally ordered pre-close claims; reports each claimed elapsed lead in
  seconds and min/max by nominal horizon. It never selects a winner, estimates
  performance or retrospectively chooses a favorable safety-margin threshold.
- Marks every timestamp and run ID as **not independently verified** and
  always returns `scientific_authorization=NO_RUN`, `stage7_freeze_authorized=false`.

Example: a synthetic nominal 1h forecast published 30 seconds before its
specified target close has **30 seconds of claimed elapsed lead**, not 1 hour.
That observation is not proof of a successful forecast, public immutable
publication or first-observed source-data availability.


## GitHub-hosted push/commit consistency (bounded real observation)

`reconcile_github_push_bundle(run, job, commit, log_lines, rows, claim_semantics)`
uses a **price-free** projection of the exact GitHub REST scheduled run, its
successful `hourly` job, the fetched pushed commit, GitHub's timestamp-prefixed
job-log `<old>..<new> HEAD -> main` line, and all four newly appended forecast
time/horizon metadata rows. It enforces same run/job identity, positive numeric
IDs (including larger GitHub job IDs), the recognized workflow and version,
checkout-head/commit-parent/push SHA consistency, bounded server-log time within
the run's GitHub creation/update window, four consistent origin and issuance
times, and the existing canonical calendar/horizon/lead checks. Mismatches
fail closed. It never fetches market data, trades, prices or predictions.

A **real** price-blind regression fixture is based on public run
[39136397235](https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/actions/runs/39136397235),
job `117701666173`, pushed commit
[`7a5599d`](https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/commit/7a5599d716dd5ce79b0d012885e08ba17c17bcd3),
and the GitHub-hosted push-line timestamp `2026-10-18T14:31:58.0994084Z`.
The 1h target closed 15:00 UTC. The push-log-to-target lead was
approximately **28m 01.90s**, not 60 minutes. However, because the successful
GitHub run's own server-provided `updated_at` was **14:32:01 UTC**, the
reconciler now conservatively uses the **later completion bound**, yielding
**1679 seconds (27m 59s)** of *claimed* elapsed lead. This protects against a
push message before maturity followed by a run completing after maturity; it
can reject otherwise timely posts but must never create false eligible posts.
`minimum_elapsed` correctly blocks the four nominal 1/4/12/24h full-lead
claims at that publication time; `bar_aligned` retains actual elapsed
durations but makes **no full-horizon representation**.

**Trust boundary: the helper is NOT an external verifier.** The returned
primary status is deliberately `GITHUB_RUN_PUSH_PROJECTION_ONLY_UNVERIFIED`
for internally ordered inputs, or `GITHUB_RUN_PUSH_PROJECTION_BLOCKED`
when temporal/coverage assertions fail. Neither status means the supplied
four forecast rows came from the claimed Git commit. In particular, a caller
can shift all four `issued_at_utc` projections consistently without
changing the commit SHA, and this metadata-only function cannot detect it.
Do not upgrade the status to content-bound unless an independent reviewer
matches exact committed forecast bytes with an authenticated Git blob/tree
and a separately witnessed server publication time.

**Trust boundary: the helper is NOT an external verifier.** The objects and
log string supplied to this function can be forged by its caller. An independent
reviewer must authenticate that each was separately fetched from GitHub's
actual API/log endpoint and that the price-free projection truly matches bytes
of the referenced append commit. The function does *not* authenticate that
projection, prove earliest public GitHub API visibility, provide a signed
immutable timestamp or approve source as-known-at vintage. The input field
`claimed_publication_upper_bound_utc` is unverified when supplied by a caller;
for GitHub-bundle reconciliation it is populated from the *completed* run's
`updated_at` rather than the log push instant. The latter remains diagnostic.
Even this conservative bound needs the run/commit/ledger identity independently
matched and externally witnessed before any scored prospective eligibility. It returns explicit
`False` authentication and first-publication-attestation flags and
`NO_RUN`, never GO. Git author/committer timestamps are not substitutes for
server evidence.

**Live-remediation prerequisite remains:** preregister a new full elapsed
target convention, never silently change old model-version meaning, bind
forecast content digest to independently witnessed publication, refuse late
or missing receipts in scoring and leave every missed origin in the denominator.
Do not change the currently scheduled runner or merge either draft based
on this metadata work alone.

## Independent review still required

A GitHub run ID and a timestamp supplied by the caller are not evidence that
GitHub actually hosted that job and text at that instant. Real use requires an
independent reviewer to fetch **GitHub-server-originated** run/step/log and
matched ledger-commit evidence, distinguish step/log emission from durable
public forecast publication, and verify every expected/missed origin.
Git author/committer dates are user-supplied metadata; a green CI or local
post-fit clock is not external immutable provenance. Independently preregister
elapsed-lead definitions, source publication cutoffs, acceptable publication
windows, a safety buffer, non-replenishment and statistical testing **before**
using price or direction outcomes. Existing A1–A6 and external custody
requirements in Issue #81 remain unverified.

Tests: `python -m pytest -q tests/test_stage6_hourly_elapsed_lead_audit.py`.
Both modes remain `NO_RUN` and are not admissible for statistical confirmation
without independently authenticated publication and preregistered provenance.
This isolated helper and its tests are synthetic and do not trigger the
`btc_hourly_live_smoke.yml` path filter or create new schedules.
