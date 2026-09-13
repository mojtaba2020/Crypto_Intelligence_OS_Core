# Phase 0 Status

## Implemented and tested

- Canonical IDs
- UTC normalization
- Strict immutable base contracts
- Structured errors and fingerprints
- Health contracts
- JSON Schema export + drift detection
- Stable Core provider-coupling guard
- Internal Python dependency graph generator
- Unit tests
- CI workflow
- Dependabot configuration

## Deliberately not implemented yet

- Market data provider
- Database
- Model provider adapters
- Agents
- Prediction Ledger persistence
- Backtesting engine
- Risk Engine
- Trading or exchange execution
- API keys or secrets

## Status label

**CI-CORRECTED FOUNDATION SKELETON — GITHUB CI RERUN REQUIRED**

This label does not mean production-ready. The first GitHub CI run exposed five static-analysis
findings in Ruff; those findings have been corrected in this package. Runtime tests and local
deterministic checks pass. A GitHub CI rerun must still pass Ruff and Mypy before this baseline
is promoted further.
