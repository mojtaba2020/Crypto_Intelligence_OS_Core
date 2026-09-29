# Hourly Independent Replication Contract V1

Research-only, fail-closed confirmation contract.

## Locked scope
- Market: BTC/USD
- Horizons: 1h, 2h, 3h, 4h, 12h
- Discovery exchange: Coinbase
- Independent replication exchanges: Bitstamp and Bitfinex
- Benchmark: persistence
- Metric family: paired absolute percentage loss
- Statistical test: null-centered paired moving-block bootstrap
- Familywise control: Holm-Bonferroni at alpha=0.05

## Required provenance
Each replication artifact must record exchange, symbol, UTC boundaries, raw/source SHA-256, code commit SHA, workflow run ID, feature version, model version, and locked sample count.

## Promotion rule
A challenger is never automatically promoted. Historical discovery, prospective confirmation, and independent-exchange replication are separate evidence layers. Missing data, missing provenance, unsupported inference adapters, failed statistical gates, or inconsistent horizon coverage fail closed to persistence.

## Anti-leakage
All features must be computable at forecast origin. Model selection cannot inspect locked-test outcomes. Replication hypotheses and horizons are fixed before inspecting replication results.
