# Stage-6 mock prefit-state transfer interface — in-memory and synthetic only

**2026-10-17 · research-only Draft · NO-GO / NO_RUN / NO_FREEZE · no real data.**

This is stacked on [Draft PR #93](https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/pull/93) at `b41f49e5fdd37e91ee3fb3713612383887db204a` (itself stacked on Drafts #92 and #91). **Do not merge** or execute an actual model fit. No workflow or public data collection changes.

The prior Ridge bridge accepted an ordinary in-memory dictionary of manually authored 1-feature mock Ridge coefficients for 13 horizons. This PR introduces a minimal **serialization/integrity boundary** for the *same mock states*:

1. Accept a strictly bounded (at most 64 KiB) **caller-supplied `bytes` object**, and a separate caller-supplied *expected SHA-256*; never accept a filesystem path, URL, trained model pickle, Python object deserialization or provider API.
2. Require exact **canonical UTF-8 JSON bytes**, with duplicate-key detection, no NaN/Infinity, no extra metadata or target labels, 13/13 exact horizon states, and explicit `classification: "MOCK_ONLY"`, `real_data_authorized: false`.
3. Validate each state's two scalar weights, one feature mean, one positive nondegenerate scale, and *claimed* model-code digest using existing PR #93 logic; make independent deterministic **local state-byte hashes** after validation. **Do not** mislabel those self-hashes as vendor signatures, official receipts or time-of-availability.
4. Send the in-memory plain validated mock-state dictionary through the **existing project's `hybrid_forecasting._estimate` numerical equation**, reached via PR #93, and the PR #91 closed output contract. Return a complete 13-horizon synthetic batch and flags that **all** authentication, real-data evaluation, licensed use, predictive skill and calibrated uncertainty remain false.

A SHA-256 match here means the caller's bytes match the caller's own claimed digest. It does **not** prove who produced those bytes, which model was fitted, whether historical input vintages were as-known-at origin T, that the SHA was independently timestamped, that the input values are legitimate real BTCUSD prices, or that any external custodian witnessed bytes.

## Attack-test acceptance checklist

- Byte cap, strict plain `bytes` only, canonical encoding; fail closed on UTF-8 errors, malformed JSON, duplicate keys and nonfinite numeric tokens.
- Detect changed bytes with an old hash, noncanonical casing/digest, malformed nested mock coefficient state, omitted horizon, unsupported source identity, late observation, forbidden extra metadata/outcomes/secrets and attempts to claim `real_data_authorized=true`.
- No path/URL, module import of pickle/cloud SDKs, byte persistence, data acquisition, training, scoring, scheduled publishing, paid resources, protected OOS or model deployment.
- True model artifacts and true externally authenticated provenance remain **out of scope**. The current validator handles only **single-feature mock Ridge states** and must **not** be used to imply that real multi-feature hybrid model checkpoints are supported. Signed offline artifact verification, larger variable-feature model metadata and strict historical source-vintage validation would each require separately reviewed designs and independent A1–A6 signoff.

**Scientific status unchanged:** Stage-6 V3 0/24 Freeze-ready, NO-GO / NO_RUN / NO_FREEZE. Keep Draft, do not merge or deploy. CI and independent Codex are software-only gates.
