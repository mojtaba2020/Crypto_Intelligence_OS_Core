# Stage-6 label-blind calendar engineering preflight (2026-10-13)

**DRAFT ENGINEERING / SYNTHETIC ONLY / NO_RUN / NO_FREEZE**

This proposal is an isolated pure Python function and deterministic synthetic tests.
It does **not** read any market dataset, validate any exchange publication log,
access Fresh Locked OOS, fit a model, unlock physical access control, define a
preregistered scientific hypothesis, demonstrate 90% direction accuracy, or
qualify even one of the original 24 tested hypotheses for Stage-7 Freeze.

This branch is **stacked on Draft PR #77** at the exact revision
`b1861b24e16ef96ae3c23575f705ae6866f6b5ed`. The protected
`research/v3-agent-wave-1`, `main`, frozen original judge and persistence
baseline remain unchanged.

## Purpose

Produce a fixed, auditable **prospective-calendar feasibility design** for the
13 user-requested horizons: 1h/2h/3h/4h/12h, 1d/2d/3d,
1w/2w/3w and 1mo/3mo.

It examines **only synthetic timestamps and completeness/publication flags**,
not OHLCV values, labels, predictions, model performance or residuals.
The closed schema rejects any extra fields; the caller cannot pass prices,
target values, feature scores or gains. A plan declares the origin start,
exclusive stop, forecast hypothetical publication lag, review as-of,
development-exclusive end and reserved-start boundary. Each scheduled origin **must** have the exact deterministic
`origin:{horizon}:{origin_cutoff_utc}` ID, so arbitrary ID text and ID
reassignment fail closed. A missing slot is an error, not quietly replenished
or compressed. The generated ID itself is *not an externally immutable*
approval: the plan, time range and its independently trusted identity still
need to be signed/fixed by a separately authorized operator.

Weekly start = Monday 00:00 UTC. Month starts = first of the calendar month
00:00 UTC, so three months never means 90 days. For all horizons the target
end is calculated from the *forecast origin cutoff* plus the declared number
of source bars. Gap/incomplete source assertions, unknown or late source
first-publication/revision, immature targets, late hypothetical forecast issue
times, or crossing the development/locked boundary exclude an origin.

**Important limits:**

- `PROVISIONAL_ELIGIBLE` means only that the **self-asserted metadata**
  passes a pure logic check. It is never proof of authenticated source
  first-publication/revision, physical isolation, immutable identities or
  legal authorization to read the input. No source hashes are authenticated.
- Even a provisional eligible count is **not independent/effective sample N**,
  is not an 80%-power result, and says nothing about accuracy, horizon
  selection, label validity, data leakage in downstream modules or profit.
- The issued-at timestamp in this prototype is **hypothetical**. It does
  not establish that any real prediction was generated and published then.
- This code never automatically backfills or retries exclusions, and cannot
  mark inputs as approved. Its output always says
  `scientific_authorization=NO_RUN` and `stage7_freeze_authorized=false`.
- The 13-horizon scoring lane and intraday model features **do not exist
  merely because** this metadata-only scheduler recognizes those horizons.

## Independent reviewer challenge — before engineering signoff

1. Try smuggling any current/future price, volume, label, return, model metric,
   or arbitrary named field into the closed plan or record schema; ensure
   it fails closed before an eligibility summary is produced.
2. Falsify hourly/daily/Monday-weekly/calendar-month cadence (including
   leap years, year transitions and 3mo target durations).
3. Attempt to omit, duplicate, substitute or reorder scheduled origins; no
   opportunistic origin replacement is allowed.
4. Test late original publication, late *last revision*, missing publication,
   unknown completeness, immature target, revised or contradictory metadata,
   target publication before expected bar maturity, boundary-crossing and
   late forecast issuance.
5. Show that "source publication verified" cannot be claimed based on a
   caller's self-description; operator A1–A6 gates and independent reviewer
   remain separate.
6. Audit the floating-point and integer timestamp paths, exception handling,
   schedule-size guard and no I/O provider or reserved-data access.
7. Run all synthetic tests on Python 3.13/3.14 and separately report a
   non-assigned **GO/NO-GO for this software preflight only**.

## Independent Codex falsification and corrective patch (2026-10-13)

The independent Codex review of the first PR #80 head
`a228635976679a69c85dd49f652e4d86f047cc90` returned
**engineering NO-GO** despite CI being green. This is a substantive software
defect, not proof the audit metadata was safe.

1. **P2: hidden outcome-bearing text channel:** arbitrary `schedule_id`
   strings could carry `close=123.45;future_return=0.42;model_MAPE=0.01` and
   get echoed into reports. The corrected function only accepts the exact
   generated ASCII `origin:{horizon}:{timestamp}` identifier and emits that
   generated value, never a caller-supplied descriptive string.
2. **P2: silent ID reassignment:** swapping distinct arbitrary IDs among valid
   origin rows previously passed. Expected identity now binds to the closed
   allowlist horizon and exact canonical time; any switch fails. *This is
   internal deterministic consistency, NOT proof of external immutable
   authorization or a frozen human-reviewed schedule.*
3. **P3: datetime support inconsistencies:** near year 9999, hourly/daily/
   weekly arithmetic could generate an out-of-range `target_end` that was
   labelled provisionally eligible, whereas monthly already failed. Now all
   supplied absolute timestamps, source/target publication timestamps,
   computed forecast-issue timestamps, and every nonmonthly advancement must
   fit the supported UTC datetime range or fail closed. Calendar arithmetic
   never silently wraps or fabricates future dates.

The regression suite explicitly includes the original malicious ID payload,
ID permutation, re-horizon tampering, invalid numeric ID, all four calendar
families near the datetime limit, publication timestamp and issue-lag
overflow, and invalid absolute plan boundaries. It remains synthetic-only.
**Fresh independent adversarial review on the post-fix commit is required**
before the software-only GO can be recorded. Existing research data
publication history, label-blindness of a real source, and the true runner
sandbox A1–A6 remain UNVERIFIED and NO_RUN.

## Future P0 operator handoff (NOT authorized by this branch)

A trusted **evidence producer**, legally entitled to the historical
development-only source, and a separate **independent reviewer** must
establish A1–A6 (exchange identity, full vintage timing and revisions,
externally pinned byte hashes, actual OS-isolated read-only mounts, reserved
alias/access denial, pinned executable/dependencies and explicit signoff).

Only after independently passing A1–A6 and confirming the origin schedule
on **approved label-blind metadata**, determine usable prospective
origin count, time dependence and statistical power. Then preregister
exactly one bounded new research comparison (or return NO_RUN).
Do not select among STATS-03 vs FEATURE-03 or the 13 horizons based on
past observed diagnostic performance.

## References

- [Existing scientific NO-GO and frozen 24-family outcome, issue #71](https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/issues/71)
- [User 13-horizon dual-target metrics contract, issue #78](https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/issues/78)
- [Research frontier as of October 12, 2026, issue #79](https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/issues/79)
- [Physical provenance and separate operator approval matrix, PR #77](https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/pull/77)
