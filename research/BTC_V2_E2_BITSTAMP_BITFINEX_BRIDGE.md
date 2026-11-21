# Stage-6 E2 — Bitstamp + Bitfinex V1-to-V2 historical readiness bridge

**Authority:** [North Star](../docs/PROJECT_NORTH_STAR_AND_EXECUTION_ROADMAP.md), [Command Center](../docs/OPERATOR_COMMAND_CENTER.md), [Issue #71](https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/issues/71), [Issue #81](https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/issues/81), [PR #62](https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/pull/62).

**Status:** Offline research-only interoperability instrument, NOT historical independently witnessed as-of evidence, training, Fresh Locked OOS, or a production Bitstamp/Bitfinex collector.

## Exact implementation

- Source: **existing V1 raw exchange artifact schema**, not a new downloader: `<exchange>_hourly.json`, `<exchange>_hourly_audit.json`, `<exchange>_daily_native.json` in `real-data/`; `<exchange>_1d.json`, `<exchange>_1w.json`, `<exchange>_1mo.json`, `prepared_manifest.json` in `prepared/` for each of **bitstamp** and **bitfinex**.
- Module: [`scripts/btc_v2_exchange_ohlcv_bridge.py`](../scripts/btc_v2_exchange_ohlcv_bridge.py).
- Output: one **separate** 13-horizon joint technical+fundamental availability audit for each exchange, plus source hashes, excluded unclosed week/month buckets and explicit `train_or_stage7_authorized=false`. Market price/volume values do **not** enter the report or the model evaluator.
- V1 SHA-256 identity, row count and sorted timestamps are checked. `source_bars/expected_source_bars/is_complete` must agree with *native daily source timestamps*; no missing candle is fabricated. Raw hourly **open** timestamps become the **following hour's close**; prepared daily, Monday-anchored weekly and first-of-month buckets are shifted to their **actual period end**, never their opening instant.
- The approved **development-only** end time must be supplied by the operator and independently confirmed against frozen/locked split boundaries. Raw inputs extending **after** this endpoint fail closed. An unfinished prepared weekly/monthly bucket can be excluded from reporting, never relabelled complete.
- E2 is **metadata feasibility only**. Reconstructed historical V1 OHLCV downloaded later does not prove the same values were known at a historical issue time. Third-party signed collection vintages, vendor licenses and independently accountable first-seen witnesses remain separate gates. An operator-supplied endpoint does not certify independent locked OOS isolation.

## Current raw evidence availability

Earlier [V1 Real Data workflow #36657053830](https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/actions/runs/36657053830) and [#36657042717](https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/actions/runs/36657042717) ran successfully on September 30, 2026. **The archived artifact lists now return empty** (30-day retention in the old workflow); therefore no verified current 2011–2026 candle counts, gap counts or real-source 13-horizon coverage can be claimed from those run results.

**Do not rerun the old `btc-multitimeframe-real-data.yml` solely to retrieve source data:** its steps also run `run_real_multitimeframe_judge_v1.py` on **locked OOS**, violating the Stage-6 separation gate for exploratory work. An isolated source-only collection/metadata preparation job with an approved development period, licensed sources, safe timeout and cost review must be designed and authorized first. No new real-data workflow, external API/GPU or protected test was triggered by this PR.

## Offline use with separately collected approved V1 artifacts

These are **operator instructions**, not evidence of a completed historical collection:

```bash
python -m scripts.btc_v2_exchange_ohlcv_bridge \
  --real-dir /trusted/preapproved-v1/real-data \
  --prepared-dir /trusted/preapproved-v1/prepared \
  --origins-json /trusted/approved-dev-origins.json \
  --fundamentals-json /trusted/verified-fundamental-observations.json \
  --approved-development-end-utc "YYYY-MM-DDTHH:MM:SSZ" \
  --output /trusted/reports/e2_two_exchange_readiness.json
```

`approved-dev-origins.json` must contain **only** `{"origins":[{"horizon":"4h","cutoff_utc":"..."}]}`, with named horizons from the official 13. `verified-fundamental-observations.json` must contain **only** `{"observations":[...]}` in the V2 strict evidence schema. Omit `--fundamentals-json` if no verified observations exist: the report then records **zero supplied fundamental coverage**, not a claim that fundamental market data did not exist.

The operator must prevent leakage of original private dataset contents, reserved market outcomes, source secrets or founder proprietary rules into pull requests. Do not publish raw V1 history or source vendor credentials as part of the report.

## Evidence and next action

- Synthetic isolated compatibility tests (10 cases): [`tests/test_btc_v2_exchange_ohlcv_bridge.py`](../tests/test_btc_v2_exchange_ohlcv_bridge.py). Dedicated CI tests run Python 3.11 and 3.13; repository CI uses Python 3.13/3.14 and is authoritative when complete.
- **Next dependency:** Obtain an explicitly approved *development-only* historical source range, then create a source-only read-and-audit pipeline decoupled from V1's locked judge. Report actual Bitstamp/Bitfinex first/last dates, gap counts, cross-venue overlap, 13-horizon valid-origin counts, missing fundamental observations and external first-seen gaps. Do not proceed to Model Freeze or claim predictive edge without separate science approvals.

**Paid experimental-agent/API/GPU ceiling remains $10 combined.** GitHub Actions minutes may have account charges not verified by this code; do not assume automatically free or trigger heavy continuous jobs.
