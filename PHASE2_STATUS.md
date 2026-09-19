# Phase 2 Status — Real Bitcoin Market Data

Status: **Candidate for GitHub CI validation**

Phase 2 adds the first real external market-data adapter while keeping the Stable Core
provider-neutral and read-only.

## Included

- Coinbase Advanced Trade public BTC/USD candle adapter behind a replaceable adapter boundary.
- No API key, account access, trading, transfer, or write capability.
- Explicit HTTPS timeouts, bounded retries, rate-limit handling, and response validation.
- Automatic pagination around the provider's 350-candle response limit.
- Conservative final-candle eligibility with a one-second public-cache safety margin.
- Strict default `SYSTEM_KNOWN` snapshot mode that rejects records ingested after a cutoff.
- Explicit `RECONSTRUCTED_MARKET_VIEW` mode for historical reconstruction so it cannot be
  confused with data the system actually knew at that historical instant.
- Coinbase server-time support to reduce local-clock dependence.
- A read-only `scripts/fetch_btc_sample.py` smoke-test command for manual live verification.
- Unit tests with mocked transport; CI does not depend on live external networking.

## Safety boundary

This phase is **market-data read only**. It cannot place orders, move funds, authenticate to
an exchange account, or execute capital decisions.

## Provider note

Coinbase is an adapter, not a dependency of the Stable Core. A future Kraken, institutional,
or archival provider can be added without changing canonical asset or OHLCV contracts.

## Provider contract checked

Coinbase documentation was reviewed on 2026-09-15. The Advanced Trade public endpoint
registry states that public endpoints do not require authentication, public responses may be
cached for one second, and the public candle endpoint returns at most 350 candle buckets per
request. The adapter therefore sends `Cache-Control: no-cache`, still applies a conservative
one-second candle availability margin, and paginates longer ranges.
