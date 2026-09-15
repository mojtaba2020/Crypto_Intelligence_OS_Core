# Phase 1 — Canonical Asset & Market Data Core

Status: TESTED FOUNDATION
Version: 0.2.0

Implemented:

- Provider-neutral canonical asset identity.
- Bitcoin and USD seed registry.
- Provider-neutral market instrument identity.
- Decimal-based OHLCV contracts.
- Explicit `available_at` and `ingested_at` timestamps.
- Point-in-time filtering and future-data rejection.
- Immutable market-data snapshots tied to a data cutoff.
- JSON Schema export for new contracts.
- Stable-Core architecture guard extended to asset and market-data modules.

Deliberately NOT implemented yet:

- External exchange APIs.
- Live streaming.
- Database persistence.
- Trading or capital execution.
- Provider-specific adapters.


## v0.1.1 correction
- Sorted the public `__all__` export list to satisfy Ruff RUF022.
- Marked `AssetClass.TOKEN` as an intentional taxonomy label so Ruff S105 does not treat it as a credential.
