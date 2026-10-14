# Stage 6: Dual-track evidence pilot (design only, 2026-10-14)

**DRAFT — INACTIVE — NO_RUN — NO_FREEZE.** This document does not authorize market-data downloads, scheduled jobs, purchases, model fitting, public redistribution, or opening locked out-of-sample data. The historical V3 result (0/24 freeze-ready) remains unchanged.

## Track H: recover what was historically knowable
Inventory sources and evidence *without* training or scoring:
- Exchange trades: distinguish event time, vendor receive time, database insertion, backfill and revised vintage. Record documented gaps and venue-specific coverage. Unknown first availability => **UNKNOWN**, never a claimed historical pass.
- On-chain BTC/USD oracles: independently inspect exact chain, verified contract/proxy and aggregator phases, round ID, log/transaction, block number and block inclusion proof, block timestamp, update timestamp, decimals, and feed availability at each proposed origin. An oracle round attests a **published oracle value**, not raw Bitstamp/Bitfinex trades, nor a precise exchange price at every 1h origin.
- Contemporaneously archived snapshots: require verifiable pre-origin publication and immutable bytes; a hash made now proves only present bytes, not earlier existence.
- Compare sources using a fixed exchange/symbol/date table. Never substitute missing markets, cherry-pick available origins, equate trade timestamps to first availability, or reuse already viewed historical outcomes as fresh independent confirmation.

**Deliverable H:** redacted matrix of (venue, period, event timestamp, first-observed vintage proof, revision history, independent custody, usage rights, gaps, verdict PASS/UNKNOWN/REJECT). Do not store raw licensed trades, keys, restricted paths or price/target rows in public GitHub.

## Track F: genuine future-origin evidence
Design a limited pilot with a future fixed UTC start, a fixed primary market, 1h observation cadence and a 1d reporting cross-check (not a 13-horizon model-comparison campaign). Keep every scheduled slot including missed, late, conflicting and outage slots; no favorable replacement or post-hoc origin selection.

Before activation, require:
1. **Written data licence** covering intended AI/cloud/commercial handling; provider endpoint and vendor coverage pinned. Tardis free samples do not imply commercial or general-purpose AI rights.
2. **Two actually separate operators/collection trust boundaries** (not two Python objects on the same host), independently calibrated UTC time sources, raw bytes captured at the request boundary, event and receipt timestamps, original byte SHA-256, request errors/disconnections and revisions.
3. **External evidence custody:** receiver cannot rewrite an already sealed original. Independent reviewer verifies exact object version/digest/retention, trusted clock evidence, permissions and no access to reserved data. AWS Object Lock is optional and potentially billable; mere self-hashes and ordinary local files are not proof.
4. **Forecast issuance before outcome:** separately pin model version, features-as-known, origin, horizon, predicted price/direction and issuance receipt **before** future maturity. Seal forecast bytes and timestamp outside model-writable custody. Quarantine labels until maturity.
5. **Statistical preregistration:** one primary horizon, baseline, metric, selection/power/multiple-comparison plan, failure budgets, STOP conditions and cost ceiling. Report all attempts including missing/outage slots; no accuracy promises. Independent effective N requires dependence-aware review.

**Deliverable F before activation:** independent A1–A6 approval packet, approved budget/licence, pinned schedule and source, dry-run with synthetic data and an external reviewer. No collector, cloud bucket, OpenTimestamps submission, automation, forecast publication or model training has been activated by this proposal.

## Decision rules
- Historical first-vintage evidence absent => Track H remains UNKNOWN, not backtested-PIT-approved.
- Supplier and infrastructure licences/approval absent => Track F stays INACTIVE.
- Success on any software or synthetic test is not exchange authenticity.
- Only a *later separately approved* prospective sequence can support genuinely new forward performance evidence. This pilot alone will not prove predictive skill or unlock Stage 7.

References: issue #81 (A1–A6), draft PR #85 (offline local receipts), draft PR #80 (calendar metadata only). Vendor licensing and source evidence must be reviewed before any new collection.
