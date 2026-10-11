# Stage-6 Wave 2: real AI research-review outcomes (2026-10-11)

**Status:** Three provider-connected bounded reviews completed successfully. Scientific
qualification remains **NO-GO** (zero of the previous 24 observed hypotheses
Freeze-ready). Neither Codex nor CatBoost training ran in this workflow.

Workflow: https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/actions/runs/38168717999
Code trigger commit: `e85a3c33a3a3d58e559d74732318fa2262217e35`.
Research branch: `research/v3-agent-wave-1`. Provider: OpenAI `gpt-5.6`.
The only evidence passed to the model was a pinned development-only brief, not
raw or locked forecasts. Provider-authored packets were validated against the
existing closed JSON schema and safety booleans.

| Job | GitHub artifact ID | JSON SHA-256 | Input tokens | Output tokens | Estimated API cost (USD) |
|---|---:|---|---:|---:|---:|
| STATS-02 | 11713295705 | `5d8624d401d5972c4b87c402efb7b3339783f0d6ab31c3ac46c5226a7b62f41c` | 1032 | 2177 | 0.047668 |
| AUDIT-02 | 11713325652 | `4ca2b880bb09ec0234d923be4caa904bf9cd7ae18f33b1badfccad1ad0d19446` | 1036 | 2189 | 0.047924 |
| FEATURE-02 | 11712924317 | `43f8144a892584b2bc21d07f708be7eb90a0c0a9294ccaa123c5241b0f8cef1f` | 1033 | 2333 | 0.050792 |

Total provider usage: **3101 input and 6699 output tokens**.
Approximate *model-token charge*: **$0.146384** at current posted
GPT-5.6 Sol standard pricing $4/million input, $20/million output.
Actual provider billing, free credits, any cache treatment, taxes and exchange
of billing terms remain authoritative. This is not a ledger balance or a
claim that the account was charged exactly this amount. GitHub-hosted Actions
standard runner in public repository is separately subject to GitHub terms.

## Independent recommendations (advisory only)

**STATS-02 — AUDIT:** Circular moving-block resampling by consecutive *index*
may bridge ~390-420 day *calendar* origin gaps. That does not prove that
original p-values are wrong. Propose a **preregistered** calendar-aware
dependence check, null calibration on the fixed *future* timestamp calendar,
and fail-closed minimum-effective-block criteria. Do not cherry-pick a
bootstrap method after seeing which one rejects.

**AUDIT-02 — AUDIT:** Reconstruct row-level source availability, calendar
completion, feature lookback endpoints, label target maturity, purging and
reserved/locked split boundaries; require no imputation or future publication
timestamps. Origin gaps by themselves do not prove leakage.

**FEATURE-02 — CONTINUE EXPLORATION:** Design a separate, shallow, seeded
CatBoost sandbox. It is **not yet trained**. Use inner time-ordered selection
and an outer development-only descriptive trial. Preregister any genuinely
independent confirmation with explicit horizon and multiplicity family.
No new result on the already inspected 24 hypotheses may be treated as
confirmatory.

## Engineer/decision checkpoints

- Issue #72 contains the Codex-ready CatBoost coding brief, including
  constraints and tests. **No Codex execution was launched from this chat.**
- First implement a deterministic timestamp lineage audit and independent
  statistical review of index-based dependence assumptions; preserve original
  unmodified Holm evidence.
- Propose CatBoost as a **separate exploratory branch** only, with no production,
  market trading, new locked OOS, or automatic Freeze.
- Agents are reviewers, not proof of profitability. Their recommendations
  must undergo source/test review and cannot override the NO-GO verdict.

There is no recurring provider trigger and no paid automatic retry in this wave.
