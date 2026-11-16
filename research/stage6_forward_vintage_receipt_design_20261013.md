# Stage 6: Forward-only observation receipt prototype (2026-10-13)

**DRAFT / INACTIVE / NO_RUN / NO_FREEZE / PUBLIC REPOSITORY.**

This small, offline Python module is a future-collector building block, not a
historical-market-provenance fix. **It has no CLI, provider network call, schedule,
API key, training loop or deployment.** Only synthetic unit tests execute on CI.

## What works

- For already received response bytes from an explicitly named
  Bitstamp/Bitfinex BTCUSD **1h/1d** source, make_local_receipt marks the
  *local process observation* with a UTC system-clock timestamp **after** bytes
  are present, and records a SHA-256 digest and byte size **without copying
  prices, raw source responses, credentials or user information into receipts**.
- Rejects unsupported source/cadence, malformed byte buffers and a supposed
  finalized-bar observation before nominal close. No user-provided historical
  first-published timestamp may be asserted.
- `save_private_receipt` is now **unconditionally DISABLED** and raises
  `PermissionError` before touching the filesystem. Independent Codex review
  demonstrated an unresolved TOCTOU directory-move attack **after** descriptor
  verification: a privileged actor can move the opened inode into the public
  checkout before the file is created. Repeated Python pathname checks or
  directory-fd operations cannot guarantee confinement against an attacker
  controlling the containing mount/rename namespace. No receipt persistence,
  collector or real-data activity is permitted in this prototype. Retained
  offline receipt creation/validation and pure synthetic inventory only.
  Restoring persistence requires a separately reviewed, OS-enforced immutable
  namespace/identity/custody design, independent operator signoff and explicit
  new authorization; not a boolean flag, user-supplied path or checklist.
- validate_local_receipt guards schema and self-checksum, rejecting forged
  authorization fields and accidental mutations.

## What this cannot prove

**System observation at X is NOT independent proof of exchange first-publication
at X.** The local system clock can be adjusted and the bytes could have been
backfilled or substituted. SHA-256 here is only a self-checksum, not a
trusted timestamp, signature, immutable external seal or trusted third-party
attestation. Local create-only files are not OS-enforced append-only custody
against a privileged actor and do not address hardlinks, mount aliases, process
credential permissions or runtime substitution. Authoritative exchange
publication/revision history remains missing for the old Stage-6 data.

For usable independent evidence an operator and a separate reviewer must
first complete [A1-A6 in Issue #81](https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/issues/81):
source/clock authenticity, revision capture, independently sealed bytes,
real OS mount isolation, pinned authorized execution identity and signoff.
A future collector must be approved *separately*, capture provider response
at the actual request boundary, log request failures and time drift, record
revisions and never backdate an arrival time. Receipts must be preserved outside
a public code repository under independently reviewed storage policy.

This code does **not** authorize launching even a free public market fetch.
No existing data pipeline, cron, model, frozen test family, main branch,
reserved/locked OOS, or Stage-7 decision is changed.

**Current scientific result:** 24 frozen V3 diagnostics -> 0/24 Freeze-ready.
NO_RUN/NO_FREEZE until provenance and prospective statistical gates pass.

## Local receipt inventory (offline, opt-in)

The companion pure module `scripts/stage6_local_receipt_inventory.py` compares
validated *local observation* receipts against an exact caller-declared 1h/1d
source/cadence/calendar plan. It has no filesystem or HTTP access and does
not read, score or fit market data. Its synthetic regression tests cover:
- Scheduled slot with no local receipt: `NO_LOCAL_RECEIPT`, **not** a claim
  that the exchange was missing that bar or that the bar is statistically usable.
- Multiple observations with identical raw-response bytes: explicit repetition,
  not multiple independent data points.
- Distinct response hashes for the same scheduled bar: `RESPONSE_BYTES_DIFFER`,
  **not** proof that OHLCV prices changed. Serialization, API metadata and
  representation can also change; real revisions need a trusted raw audit.
- Identical receipt replay, off-schedule or wrong-source receipts and
  unexpected fields: fail closed. All outputs retain NO_RUN/NO_FREEZE,
  no third-party attestation and no hidden origin replenishment.

Plans and receipts are self-asserted and do not establish completeness,
authentic clock time, independent immutable custody or an authenticated
first-publication history. This is a **local quality inventory only**, not
a scientific eligibility count or authorization to activate collection.
