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
and the fixed `(1, 4, 12, 24)` bar-horizon family. Each record identifies a
claimed scheduled GitHub run, completed-bar origin, horizon, local issue
instant, claimed GitHub log observation, and target close. It:

- Enumerates **every** scheduled `(origin, horizon)` including absent claims.
- Rejects noncanonical horizons, duplicates, target-close inconsistencies,
  cross-origin run-ID reuse, cross-run origin replenishment, prices and outcomes.
- Retains invalid, immature or late claims **as blocked/unknown categories**,
  never silently discards them from scheduled denominators.
- Computes `target_close - claimed_github_log_seen_at_utc` **only** for
  internally ordered pre-close claims; reports each claimed elapsed lead in
  seconds and min/max by nominal horizon. It never selects a winner, estimates
  performance or retrospectively chooses a favorable safety-margin threshold.
- Marks every timestamp and run ID as **not independently verified** and
  always returns `scientific_authorization=NO_RUN`, `stage7_freeze_authorized=false`.

Example: a synthetic nominal 1h forecast published 30 seconds before its
specified target close has **30 seconds of claimed elapsed lead**, not 1 hour.
That observation is not proof of a successful forecast, public immutable
publication or first-observed source-data availability.

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
This isolated helper and its tests are synthetic and do not trigger the
`btc_hourly_live_smoke.yml` path filter or create new schedules.
