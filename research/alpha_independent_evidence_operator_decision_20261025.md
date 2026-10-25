# Alpha Discovery: independent evidence operator decision — 2026-10-25

**Decision:** use a **two-witness** path, not timestamping alone. An exact-byte
**public-retrieval witness** and a separate authenticated **market-source
first-arrival custodian** are both essential for a valid forward-only BTC
pilot. RFC3161 timestamping is an optional cryptographic additional bound,
**not** a substitute for either witness. This document chooses the technical
acceptance path, **not a provider, price feed, credential, independent reviewer,
or authorized trial**. Status: **OPERATOR_UNASSIGNED / NO_RUN / NO_FREEZE**.

## Why the existing proofs cannot be promoted

**Critical schema mismatch:** Draft PR #90's RFC3161 verifier expects a
signed bundle of **four different horizons (1h,4h,12h,24h)** using the old
hourly versioned calendar. The new Alpha pilot instead requires **one
approved 4h horizon with four named forecast variants** (candidate, nested
ablation, linearized placebo, persistence). Reusing that code/schema
unchanged could certify the WRONG experimental message and wrong clock
bound. It is therefore **not an approved drop-in sealer** for the Alpha
pilot. Do not combine the old four-horizon rows with this new experiment
or retrofit them as supposedly fresh predictions.

Our legacy V2 hourly ledger and GitHub run/push timestamps do not show a
third-party first-public retrieval of the exact prediction bytes. Existing
draft PR #90 verifies *caller-supplied* Git append objects and synthetic
RFC3161 proof chains. The work is valuable for integrity, but none of it
independently establishes first-observed BTC source data, independently
approved signer identity, or actual public retrieval before the forecast's
full-elapsed target deadline.

**Key outside options reviewed from primary documentation (2026-10-25):**

| Candidate | What the service supports | What it DOES NOT prove and what must be approved |
| --- | --- | --- |
| [DigiCert RFC3161](https://knowledge.digicert.com/general-information/rfc3161-compliant-time-stamp-authority-server) | Signed timestamp for a content digest; published endpoint `http://timestamp.digicert.com` | No confirmation the file was publicly GET-accessible, or that BTC source candles were knowable. DigiCert reports responder **certificate replacements on 2026-09-03**: independently preapprove current signer/chain/policy, validity and revocation handling; do not pin historical certs by assumption. Service usage/fees not established for this project. |
| [Sectigo RFC3161](https://www.sectigo.com/resource-library/time-stamping-server) | Timestamp service for content/signatures | Same publication and source-vintage gaps. Policy/terms, current certificate and acceptable clock accuracy must be independently approved before using; not established as unrestricted/free for this use. |
| [OpenTimestamps](https://opentimestamps.org/) | Free no-registration calendar commitments to Bitcoin; eventual independently verifiable existence proof | A delayed blockchain inclusion cannot automatically guarantee the **15-minute issuance/public-availability window**, and commits a **hash, not public content**. Not a realtime GET witness; do not treat calendar acknowledgment as evidence of archived forecast accessibility. |
| [Internet Archive Save Page Now](https://wiki.archiveteam.org/index.php/Internet_Archive/Save_Page_Now) | Independent web-page capture can sometimes prove a response had become externally retrievable | Snapshot timing, preservation of byte-identical API/JSONL bodies, crawler completion and availability are not guaranteed; **not approved** as sole critical-path witness without a successful authenticated, independent preflight. |

[RFC3161 specification](https://www.rfc-editor.org/rfc/rfc3161) authenticates
time of a hash/signature under its approved trust model, not claims about
public website availability or unobserved exchange history.

## Exactly one eligible future 4h experiment — receipt contract

Proposed origin `S` every 4 hours at 00/04/08/12/16/20 UTC, feature
bar **complete** at S, forecasting payload published no later than
`S + 15 minutes`, five-minute target close `T=S+4h15m`.
Both clocks and witness response-bound accuracy must imply
`public_first_observed_upper_bound <= S+15m` and
`T - public_first_observed_upper_bound >= 4h`.

A successful independent-publication receipt **must** bind, under the
custodian's authentic, independently approved identity:
1. Exact full response bytes (SHA-256) of the public GET resource, unique
   immutable prediction URI, content length, schema version, scheduled S,
   predeclared target T, model/parameter digest, candidate + both controls
   + persistence, and interaction-active/fallback status.
2. External server clock **UTC observation interval [lower, upper]**,
   uncertainty/source accuracy, HTTP response status, independent GET
   witness identity and signature/integrity method, receipt verifier and
   expiration/revocation policy. No caller-supplied `issued_at` proves this.
3. WITNESS-OBSERVED public GET, **not** developer-produced screenshots,
   owner-side push log, hashed private bundle, merely successful DNS/TLS,
   or a self-created local receipt. Private signing keys or protected data
   MUST NOT be committed to this public repository.
4. Every predeclared slot must be retained even if missing, late, blank,
   invalid, witness unreachable or stale. If the witness cannot GET the
   exact bytes before the deadline, that origin is **UNVERIFIED_OR_MISSED**,
   never silently dropped or counted as success.
5. Separately, independent source owner proves the **actual** BTC-USD
   pair, venue, target-bar close convention, first receipt per candle and
   revisions. Forecast labels may be scored only after independently
   witnessed target availability.

**Practical preflight before accessing any market outcomes:** external
operator hosts a harmless fixed synthetic JSON/JSONL test resource with
non-financial values and a declared hash, then independent witness records
its GET bytes/timestamps/clock-accuracy; verifier checks digest and 15-minute
bound. This is only an **external delivery feasibility test**, NOT alpha
or independent scientific proof. Any operator/provider cost or contract
requires prior explicit authorization.

## Decision states and stopping rules

- `WITNESS_OPERATOR_UNASSIGNED`: current state. No false "verified" or
  "success"; no real forecast dispatch.
- `PUBLIC_GET_PREFLIGHT_FAILED`: retain failed receipt; change provider
  or pause, not the deadline after seeing outcomes.
- `PUBLIC_GET_PREFLIGHT_PASSED_TECHNICAL_ONLY`: independently verified
  synthetic delivery only; **still NO_RUN** without independent market
  source, isolated execution, signed preregistration and statistical power.
- `PILOT_EVIDENCE_APPROVED`: **only** after all independent A1–A6 operators
  verify the actual proposed environment and before first fresh eligible
  target is exposed. The assistant, Codex, this MD file and green CI
  cannot self-approve.
- `MODEL_EDGE_PROVEN`: reserved for powered, preregistered prospective
  results with agreed multiple-comparison adjustment and full slot coverage.
  Explicitly **NOT** the current project status.

**Next external action:** assign one real source operator, one distinctly
independent public-GET custodian and independent statistics/security
reviewers; approve their restricted evidence channel; perform only the
synthetic GET preflight. Record a safe redacted verdict in Issue #81,
not fabricated signatures or JSON "CLEAR" reviewer names.

Cost budget this round: **$0 in tool/provider calls; no paid third-party
request, no new training, no live trial, no remote agents.**
