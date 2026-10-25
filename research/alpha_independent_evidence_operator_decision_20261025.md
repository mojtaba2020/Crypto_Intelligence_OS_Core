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


## 2026-10-25 narrowing: zero-cost *technical* external-GET feasibility

**Leading $0 preflight candidate, not an approved independent scientific
witness:** PingPane (https://www.pingpane.com/ and
https://www.pingpane.com/manual/getting-started). Its published free
plan has three monitors with a 5-minute check interval, no credit card,
HTTP status/response time/body hash per check, and a public status page.
The private monitor view advertises the latest 1,000 checks. This could
provide a genuine **external-network GET** after we publish a fixed,
nonfinancial synthetic test resource and authorize a separate real
operator/account.

**Verification still missing:** it is NOT established that PingPane
exposes the *full per-check exact SHA-256 and externally credible UTC
observation bound* in a third-party-readable, exportable, tamper-evident
receipt; a public uptime status indicator is insufficient. It is also
unverified whether a static immutable file can be monitored separately
for each new forecast resource without manual creation, whether checks
are reliably scheduled before S+15m, and whether an independent
custodian (not the developer) can control the account. A 5-minute poll
does not itself certify the collector's clock, original publisher or
market candle first-arrival. **Do not enable a live model on the basis
of signup or an uptime-green badge.**

**Actionable, no-cost preflight gate:** an authorized operator, using
their own separate account and ONLY innocuous synthetic content:
(1) point one $0 monitor at one permanently public immutable URL
(2) retrieve a genuine check record after a fresh external HTTP GET
(3) establish that its **exact body SHA-256** equals an independently
known local file hash
(4) independently validate UTC observation time **upper bound** (not
only local UI-rendered time), retention, signature/receipt integrity and
public availability of the evidence to a separate reviewer
(5) document missed/unavailable checks; do not count them as successes.

If 3–4 cannot be demonstrated, PingPane is **not an accepted custody
solution**. Stop that vendor and compare alternatives rather than
spending on an untested $19 one-shot archive or paid blockchain calls.
The technical preflight itself cannot grant `PILOT_EVIDENCE=APPROVED`.

**Paid fallback discovery, NOT chosen for purchase:** FreshProof's
public MCP description advertises a *fresh public-network fetch*
(`max_age=0`) with HTTP response body SHA-256 and a verifiable stored
Proof Receipt; however its observe/verify_url tools **cost money
in USDC on Base**, and operational/signer/time attestation have not
been accepted by an independent custodian. Never invoke paid
tools, sign up, or spend project funds without explicit
permission. References:
- https://glama.ai/mcp/connectors/io.github.ricksporto/freshproof/tools/verify_url
- https://verifymcp.io/servers/ricksporto-freshproof/freshproof

**Decision:** select only a *free synthetic PingPane feasibility check*
as the first external onboarding path. No account connection or
synthetic GET was performed here because no separately controlled,
authorized PingPane account or external witness is connected. This
remains `WITNESS_OPERATOR_UNASSIGNED / NO_RUN`.


## October 25 exact-byte canary — PUBLISHED / EXTERNAL GET NOT YET PROVEN

A deliberately **non-financial, non-model** one-line UTF-8 JSONL fixture
was actually committed to the existing Draft PR branch (NOT main):

- Immutable Git commit: `f5c180aa1842b0680dde4dd7442a30d890c13583`.
- Public-resource candidate: `https://raw.githubusercontent.com/mojtaba2020/Crypto_Intelligence_OS_Core/f5c180aa1842b0680dde4dd7442a30d890c13583/research/alpha_public_get_canary_20261025.jsonl`
- Schema marker: `alpha-public-get-canary-v1`, `SYNTHETIC_ONLY_NO_RUN`.
- **Expected length**: 367 bytes; **SHA-256**:
  `2ddb60f2003011b89502534c7fd20dbc0ccb28a2d1918da520001d048560eaaf`.
- Git blob SHA-1:
  `51294b5f9894a02cd93f5b3fef6a491d9a2a8141`.
- Exactly one LF-terminated JSON line. Hashes were computed
  locally and the blob identity agrees with the **connected GitHub**
  file/immutable-commit read.

**Observed limits:** Our ordinary web fetch could not retrieve that
fresh GitHub/raw URL from this execution environment (`DisabledError`).
The separate sandbox network fetch was blocked by DNS; the GitHub
connector did read the file, but its authorized connector access
**is NOT an independently attested unauthenticated public GET**.
Therefore the accurate decision is:

`SOURCE_REPO_BLOB_VERIFIED=YES`;
`EXTERNAL_PUBLIC_GET_WITNESSED=NO`;
`SIGNED_FIRST_PUBLIC_AVAILABLE_TIME=NONE`;
`TECHNICAL_PREFLIGHT=BLOCKED`;
`PILOT_EVIDENCE=BLOCKED`;
`NO_RUN/NO_FREEZE`.

This synthetic canary is ready for **one** external witness operator's
real fresh GET; the operator must independently retrieve the immutable
link and submit a time-bounded, verifiable SHA-256 receipt. The fact
that GitHub reports a commit date, the connected connector returns
its file bytes, or a monitoring page displays green is NOT a substitute.
If PingPane cannot supply accessible per-check exact-body hashes,
bounded trustworthy UTC times and separately attestable records, this
vendor must be rejected rather than upgraded to Pro.

**No account was created and no external monitor/scheduler was enabled.**
