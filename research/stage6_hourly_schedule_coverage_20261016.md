# Stage-6 hourly forecast schedule coverage: offline evidence audit

**DRAFT / NO_RUN / NO_FREEZE. No live market feed, model fitting, prices,
scored outcomes, external GitHub API calls, or active workflow edits.**

The existing `BTC Hourly Prospective Forecasts` schedule is `9 * * * *`, but
a GitHub Actions review of the **full UTC day 2026-10-16** returned just six
scheduled, successful hourly runs (at approximately 01:15, 07:04, 12:20,
17:21, 21:00 and 23:31 UTC), against 24 canonical hourly origins.
Their GitHub job logs show distinct source-hour origins of 00, 06, 11,
16, 20 and 22 UTC, each issuing the four hourly horizons 1, 4, 12, 24.

This is **6/24 observed origin slots**, **18/24 absent** and 24 out of
96 expected forecast rows on the fixed four-horizon schedule. An absent
forecast is NOT a failed price prediction, but absence must be visible:
do not silently impute, backfill, refill on a later origin, or report the
six as if they were 24 independent scheduled observations.

Three cross-checked GitHub-hosted witnesses:
- https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/actions/runs/38939066729
  printed all four forecasts around 17:21:48 UTC; first target closed
  at 18:00 UTC; exact forecast rows committed as `6b3075fec55757d6b28809a5ec182cc1a2e4e815`.
- https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/actions/runs/38966255676
  printed around 21:00:14 UTC; first target closed at 22:00 UTC;
  rows committed as `49ec0db82484646432bc4eaddc719092d7b7b808`.
- https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/actions/runs/38981863365
  printed around 23:31:23 UTC; first target closed at 00:00 next day;
  rows committed as `f1cc877360de0f0922948e771692f62e5615c6de`.

This is **limited public GitHub log/commit evidence** of publication before
the specified future bar closed, not an exchange feed authenticity
certificate, cryptographically sealed model snapshot, independent
collector-clock proof, or statistical performance result. Git commit
author/committer times are self-declared; prefer server-hosted job logs
for external timestamps, with exact log-to-commit content matching.

The pure helper `scripts/stage6_hourly_schedule_coverage.py` and synthetic
tests accept only bounded price-free metadata claims for one fixed UTC
schedule and all four horizons, reject duplicated/out-of-schedule/late
entries, and enumerate **every missing or partially filled origin**.
All outputs state `independent_github_log_provenance_verified=false`
and `scientific_authorization=NO_RUN`. There is no code path for
market-data acquisition or automatic promotion. Real operator evidence
and A1–A6 remain absent. Frozen V3 is still 0/24 freeze-ready.

**Follow-up:** independent reviewer verifies real GitHub-run provenance
for each claimed forecast, records expected scheduled slots including
misses and outages, and studies both GitHub schedule delivery reliability
and effective dependence-aware forecast sample size. Do not treat
successful CI as a substitute for these independent approvals.

## 2026-10-22 — Prevent falsely reconstructed hourly forecast batches

Review of the original price-free coverage helper found that four separate GitHub
runs (or four different claimed issuance times) could be stitched into one
`CLAIMED_COMPLETE_UNVERIFIED` hourly origin. The research-only Draft branch now
rejects those contradictions explicitly:

- Each origin's four horizons must carry **one identical GitHub run ID**
  and **one identical claimed issuance time**.
- One GitHub run ID cannot be recycled across unrelated scheduled origins.
- Claimed issuance must be **strictly after** the completed source bar's
  close, not equal to that close.
- The origin denominator remains fixed and incomplete/missed origins stay
  visible. Passing internal checks still produces `UNVERIFIED_COVERAGE_ONLY`,
  **not independently witnessed publication, full elapsed H-hour lead, market
  predictive performance, or Stage-6 approval**.

Five synthetic regressions exercise both mixed-run/time cases, reused run
identity, source-close equality and a complete but still-unverified packet.
This audit retains the **legacy bar-aligned** target definition; it cannot
certify the proposed full-elapsed label/calendar of PR #90. No network
requests, real candles, scoring, protected OOS, production runner/workflow,
merges or paid actions were performed. External custody and A1–A6 remain
separate mandatory evidence; `NO_RUN / NO_FREEZE`.
