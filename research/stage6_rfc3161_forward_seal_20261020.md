# Stage 6 — RFC3161 independent-time candidate (offline only, 2026-10-20)

## Explicit scope and scientific gate

This is **working cryptographic verification code plus synthetic signatures**, not a
production timestamp service, external witness proof, retrospective market
provenance, new trained model or authorization to score locked OOS. Nothing is
dispatched; no provider is called or paid. Historical Stage-6 remains
**NO-GO / NO_RUN / NO_FREEZE, 0/24**. This work belongs to a prospective **new,
separately preregistered** lane; it cannot relabel old \`hourly-hybrid-ridge-v2\`
records or fabricate point-in-time history.

\`scripts/stage6_rfc3161_seal.py\` verifies RFC 3161 TimeStampResp DER plus
the original request with OpenSSL. It checks **both** request/token (to match
nonce and imprint) and response/original exact forecast bytes. It requires
SHA-256, a predeclared TSA policy OID, a pinned SHA-256 hash of the exact
trusted CA PEM bytes, valid OpenSSL TSA certificate-chain/signature validation,
a granted status, one signed UTC \`genTime\`, and full original byte imprint.
It accepts only bounded byte inputs, uses a local ephemeral temporary
directory, and invokes a fixed allowlist of local OpenSSL commands with
\`shell=False\`, no network and no external providers.

The code derives *signed generation time* from a verified token, never from
a caller-supplied \`issued_at\` or GitHub run clock. It uses nanosecond integer
arithmetic so the target's minimum elapsed lead cannot gain a second through
rounding. Any invalid certificate/signature, wrong query nonce, wrong payload
or pinned root, missing/malformed time, unrecognized hash algorithm, wrong
TSA policy or short elapsed lead is **rejected or blocked**. It never returns
price values, model outputs or scored performance.

## New target and label semantics — version change required

Define \`O\` as the UTC hour **OPEN** of the most recent completed 1-hour
source candle. The source close is \`O + 1h\`, and a new model's production
forecast is sealed **after** that candle is actually available and computed.
For each \`H\` in (1,4,12,24):

- New target *bar open*: \`O + (H + 1)h\`
- New target *bar close*: \`O + (H + 2)h\`
- Training target row shift relative to source index \`O\`: **H + 1**, not H
- Allowed latest signed receipt for a genuine H-hour minimum lead:
  \`signed_genTime <= O + 2h\`.
- The same receipt must be after the completed source close \`O + 1h\`.
  If it misses the allowed window, the whole advertised full-horizon claim
  is ineligible; retain the missed origin in the scheduled denominator.
- For a real **publicly actionable** prediction, an additional independently
  verified public publication deadline and exactly matching committed bytes
  are required. A signed private hash does **not** prove the forecast was
  publicly visible or actionable.

This mathematical correction is **not yet applied to any live producer or
training label**. Retrain as a separately named model; do not alter old
forecast ledgers or mix the estimands.

## What a valid TSA trust chain does and does not prove

The CA certificate and expected SHA-256 fingerprint must be approved and
recorded **independently before forecasts and outcomes**. A caller is able
to supply its own self-signed certificate with a matching fingerprint, so
the helper explicitly returns
\`trust_root_independently_preapproved_by_this_function=False\` and always
\`scientific_authorization=NO_RUN\`. Synthetic tests create a disposable
self-signed test CA/TSA with the critical \`timeStamping\` EKU. They show
signature and nonce validation, **not** actual external attestation.

A future independent review must additionally establish the TSA's
identity, certificate validity/revocation status, acceptable policy, trust
anchor custody/rotation and timestamp accuracy guarantees. The code does not
do an OCSP/CRL online check; its output says so. Do not claim that even a
validly signed token proves the *earliest* publication or original market-data
capture in years before the receipt. Certificate-chain validation uses the
explicit pinned root supplied to the verifier, never silent promotion of a
source's own timestamp into independent provenance.

Critically, the RFC3161 tool alone cannot bind the signed payload to the
committed forecast append. The already-existing PR #90
\`bind_supplied_git_commit_tree_chain\` needs to verify the actual parent
and child GitHub commits, all tree leaves, exact forecast blob bytes and
four appended rows; the **exact appended byte range** must then be compared
byte-for-byte to this RFC3161-signed payload. Neither helper authenticates
GitHub TLS/REST independently, and no live workflow integrates them yet.
For independently witnessed public publication, a distinct trusted service
must attest the posted bytes and server observation time.

### Synthetic tests performed without a network service

The new tests generate an ephemeral RSA test root and an X.509 TSA leaf
whose extendedKeyUsage is critical \`timeStamping\`; generate a SHA-256
RFC3161 query with a random nonce; sign a mock four-horizon payload using
OpenSSL locally; then verify request nonce/imprint, exact original content,
configured trust chain, policy OID and new target calendar. Negative tests:
payload changed with original hash; payload changed and hash recomputed; CA
PEM tampering; different policy OID; non-hour-aligned origin; signed token
generated too late for a selected old origin; and **independent re-issued
query nonce** on unchanged data. No real forecast/price or saved private key.

OpenSSL reference: https://docs.openssl.org/master/man1/openssl-ts/
Protocol reference: https://www.rfc-editor.org/rfc/rfc3161

## Before real-world experimentation (not approved by this PR)

1. Preregister a new model version, label shift, fixed target calendars,
   origin denominator, missing-slot policy, comparison baseline, and
   selection/multiplicity design using **development-only** information.
2. Independently select a truly third-party TSA and preapprove/pin its
   certificate-chain and policy OID. Evaluate terms/availability, costs
   and certificate revocation, but do not subscribe or send requests
   without permission. Reject synthetic or self-signed trust anchors as
   external evidence.
3. Bind exact four-row serialized forecast bytes to real Git commit
   path/blob/parent identities, then obtain and persist a corresponding
   externally signed time before the full-horizon deadline. Check
   signature, request nonce, SHA-256 imprint, trusted signer and
   signed generation time **after** the source candle close.
4. Separately capture independently verifiable public publication of the
   *same bytes* before targets mature. Count missing/rejected attempts as
   missed scheduled origins, **not successes by omission**.
5. Only with the relevant A1–A6 scientific controls certified by a second
   reviewer may any new predictive comparison or Freeze be considered.

### Explicit Git forecast version contract (offline only)

The existing PR #90 append-only price-blind Git-byte audit now accepts two
mutually exclusive **explicitly named** versions and rejects mixing them in a
four-forecast batch:

- Legacy `hourly-hybrid-ridge-v2` retains exactly its old target calendar
  `target_hour = O + H h`, `target_close = O + (H+1)h`.
- **Proposed and UNTRAINED** `stage6-hourly-full-elapsed-v1-research-only`
  requires `target_hour = O + (H+1)h`, `target_close = O + (H+2)h`;
  the corresponding training-label shift is `H+1` bars. Every one of the
  four appended rows must declare this version consistently.

Synthetic tests verify both valid versions and reject old-model relabeling,
unshifted new-version target bars, and mixed-version batches. **This is
schema-only support**; it does not train this new model, run production
forecasts, authorize OOS evaluation or independently authenticate publication.

### Adversarial signer identity and signed-epoch checks

After independent Codex P2 findings, the verifier now extracts the **actual**
CMS signing certificate from the TimeStampToken and compares its SHA-256
DER certificate fingerprint to `expected_signer_cert_sha256`, a separately
predeclared fingerprint. A different, valid TSA signing certificate issued
by the *same* trusted CA is a hard failure, even with the same message
imprint and query nonce.

The token's as-yet-untrusted `genTime` is used solely to select the OpenSSL
`ts -verify -attime` certificate-validity epoch. Nonce/query verification
and exact full-content verification both run at that epoch, with both floor
and ceil seconds required for fractional token times. This is an offline
cryptographic test under a synthetic root, not evidence that an external TSA
actually received bytes in real time; the trust-anchor approval, revocation,
time-service policy and independent public release must still be established.
`tsa_signer_independently_preapproved_by_this_function=False` and
`scientific_authorization=NO_RUN` remain unchanged.

### Critical P2 closure — no origin relabeling of correctly signed old forecasts

The independent Codex review of the 217-test version identified that callers
could supply a **new** source origin when verifying a token issued over
**older forecast bytes**, making the time arithmetic appear eligible. This
was a real label-laundering weakness. The verifier now requires the signed
imprint to cover an exact, canonical four-row JSONL forecast bundle containing
the **new versioned full-elapsed model**. The verifier independently extracts
and validates each row's UTC `origin_hour_utc`, H+1 target hour, H+2 target
close, and shared issuance time; it refuses caller source-origin mismatches,
mixed generations, extra/missing records, duplicate JSON keys and malformed
timestamps before assigning any `signed_minimum_elapsed_eligible` flag.
A token signed now over legitimately old-origin rows **remains ineligible**
instead of accepting a newer caller-selected origin.

Tests generate synthetic four-row forecast JSONL before signing with an
ephemeral local CA/TSA. They specifically (1) reject attempts to relabel
a valid token's old origin, (2) sign *actual old-origin* synthetic forecasts
now and preserve BLOCKED status, (3) reject signed target-close mismatch
with a valid signature, and (4) reject duplicate signed origin keys. This
proves only **internal signed-bundle/calendar consistency**; no real external
TSA, production model, trusted timestamp deployment, immutable public posting,
source market vintage or Stage-6 GO is implied.
