# Crypto Intelligence OS — NORTH STAR / Single Source of Truth

**Status:** project-wide navigation and execution governance
**Recorded:** 2026-11-20 (Houston time)
**Owner's directive:** Do not drift from the previously agreed roadmap. Each action must demonstrably advance the final Bitcoin forecasting goal; incidental bugs, deployment details, or shiny model families must not silently replace the program.
**Scope:** Documentation and priorities. This does **not** authorize paid API use, model promotion, unfreezing held-out data, trading, or modifying protected experiments.

> **North Star:** Build a reliable, scientifically evaluated, multi-timeframe BTC/USD decision-intelligence system combining long historical OHLCV/price cycles with point-in-time available macroeconomics, ETF flows, on-chain signals, derivatives, news/narrative, and regime-aware features. Forecast **price, up/down/flat direction, and uncertainty** before the target occurs; store immutable issuance/outcome receipts; compare **Human vs AI vs Hybrid** and learn from prospective performance. Accuracy must be *demonstrated*, never promised.

## A. Hierarchy: two views of one roadmap

### Six original product/research phases
1. **Foundation** — mission, code/repo, baseline rules and evidence policy. Initial work built.
2. **Data & Baseline** — historical OHLCV, data quality, train/validation/OOS boundaries, Persistence. Initial infrastructure built.
3. **V1** — early technical feature and model prototypes. Initial research completed, NOT proof of alpha.
4. **V2** — classical challenger comparisons. Experiments completed; no statistically qualified winner.
5. **V3 multi-agent research** — **CURRENT PRODUCT PHASE**; research agents and 13-horizon lab in separate branches. Continue the scientific Stage-6 program within this phase.
6. **Model champion / final integration / deployment** — NOT reached; requires independent confirmation, reliable forecasting, guarded release, risk management and paper operation.

### Ten scientific research gates
1. Foundation — infrastructure / problem definition.
2. Data & Baseline — data pipelines and benchmark.
3. V1 — initial models and features.
4. V2 — classical competition.
5. V3 — agent-guided features/models.
6. **Robustness & Falsification — CURRENT SCIENTIFIC GATE; NO-GO for the previously observed 24-family cycle.**
7. Model Freeze — **NOT AUTHORIZED** until new independently sufficient evidence meets prespecified criteria.
8. Fresh Locked Out-of-Sample evaluation — reserved, not for tuning.
9. Independent exchange replication — not satisfied.
10. Genuine prospective evaluation and operational readiness — not satisfied for multi-horizon system.

The 2026-10 V3 6-horizon x 4-ablation family had **0/24 freeze-ready** candidates; the protected Persistence benchmark remains. See [Issue #71](https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/issues/71) and [Issue #78](https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/issues/78).

## B. Scope and 13 forecast horizons

Official 13-horizon research charter: hourly **1h, 2h, 3h, 4h, 12h**; daily **1d, 2d, 3d**; weekly **1w, 2w, 3w**; calendar-month **1mo, 3mo**. Additional **6mo/1y and multi-year cycles** remain exploratory/descriptive unless separately approved and statistically powered; do not silently omit or overclaim them.

Per horizon produce:
- Point price and log return, up/down/flat direction and an uncertainty interval.
- Timestamped forecast with model and dataset hashes, source venue, cutoff and target maturity; write-once forecast and published receipt.
- Paired price error vs Persistence, honest unconditional direction/coverage, nonoverlap-aware inference, interval calibration, performance by volatility/regime; no denominators hidden by abstention.

**>90% directional accuracy is an aspiration only**, not an achieved result or authorized promise. A small short-horizon gain or green CI is never scientific promotion evidence.

## C. Nonnegotiable parallel workstreams

**Track A — Historical & Technical:** 2011 onward where legitimately covered, hourly/daily/weekly/monthly OHLCV, momentum, structure, volatility, volume, halving, market-regime and user-proposed cycle *hypotheses*. A few historical missing candles should be documented and affected windows excluded—not fabricated and not a reason to abandon the whole project.

**Track B — Fundamental & Macro:** CPI/FOMC/payroll surprises with correctly timestamped expectations and revisions; USD, yields, liquidity; ETF flows at actual publication time; derivatives funding/open interest/options; Bitcoin on-chain, miners, exchange flows, tokenomics and ecosystem events; confirmed news, narratives and sentiment. Do not assume signs/causality. No retrospective vintage is allowed to masquerade as observed first-seen timestamp. Respect provider license and custody.

**Fusion:** Compare (a) Persistence, (b) price/volume only, (c) +macro, (d) +ETF/derivatives, (e) +onchain, (f) +news, and (g) fixed, preregistered full fusion at matched origin/horizon clocks. Feature transforms fit on permitted **train folds only**. Show missingness, overlap, price-error deltas, direction, uncertainty and abstention. Do not train with unverified source vintages or reserved labels.

**Product core:** independent Human/Mojtaba hypothesis, independent AI prediction, then controlled Hybrid result; timestamp and lock all three before outcomes and measure regime-dependent performance. Founder-specific proprietary rules stay confidential.

## D. Ordered execution plan (the default next actions)

### E1 — Restore forward-study reliability (operational, without retuning or invalidating it)
- Diagnose actual scheduling/runner/credential/data-publication causes for failed official 4h forecast slots; preserve all misses and the original 30-day engine/protocol/hashes.
- Change scheduling/infrastructure separately only when permissible and document exact effect; never backfill a missed forecast with hindsight.
- At the **2026-11-20 19:36 Houston** report, only **2/71** scheduled origins had valid issued forecasts and **69 were missed**. This is an operational failure requiring attention, not model accuracy evidence.
- [Issue #111](https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/issues/111).

### E2 — Finish label-blind data readiness, in parallel with E1
- Make technical dataset continuity and per-horizon source coverage manifests; document actual historical start/end, gap policy, freshness, release timestamps, revision/vintage authenticity and legal rights.
- Keep a separate source custodian/witness decision path; Issue #81 is a **scientific independent-custody gate**, not a ban on transparent isolated exploratory engineering.
- Use bounded Stage-6 coverage auditor plus CI, not fabricated historical first-seen claims.
- [PR #62 multi-timeframe lab](https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/pull/62), [PR #117 point-in-time news/fundamental prototype](https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/pull/117), [Issue #81](https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/issues/81).

### E3 — Specify candidate roster & evidence design BEFORE confirmatory test
- Reuse V1/V2/V3 historical reports. Candidate controls include Persistence, prior sign/always-up; bounded classical candidates include Ridge/ElasticNet/RandomForest/ExtraTrees/HistogramGradientBoosting and CatBoost only if justified.
- TimesFM/Chronos are **optional** shadow challenger research requiring license/runtime/cost confirmation, not default mandatory installs or proof of BTC alpha.
- Agent-generated hypotheses must be preregistered with exact feature availability, fixed splits/cadence/purge/maturity, benchmark, statistical sample adequacy, multiplicity and prospective confirmation. Never retune on previously inspected October/held-out results.
- [Issue #71](https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/issues/71), [Issue #78](https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/issues/78).

### E4 — Execute bounded technical-vs-fundamental-vs-fusion experiments
- Only on approved development data; compare same model class/forecast origins and registered feature ablations per family/horizon.
- Run reproducible CI and controlled research agents; collect loss series, missing/late origin counts, feature lineage, independent audit.
- Keep 13 horizons distinct; 6mo/1y/multi-year exploratory until adequately powered.

### E5 — Stage-6 decision
- Independent scientific review plus leakage/security audit; credible positive paired improvement with dependence-aware intervals and preregistered corrected inference, adequate independent observations, source provenance and restricted data isolation.
- **GO -> propose Stage-7 manual Freeze** only if all gates pass; **NO-GO -> clearly document and improve novel hypotheses on eligible future evidence**. No automated promotion to production.

### E6 — Stages 7-10, then product expansion
- Freeze winner identity+features+weights+data+code, evaluate once on truly untouched locked OOS, replicate across independent exchanges, issue genuinely prospective forecasts, measure coverage/direction/price/interval calibration and reliability over time.
- Only after evidence: engineering deployment, app/dashboard, history, alerts, human/AI/hybrid weights, paper trading, risk rules/kill switch, opt-in product features, user accounts/subscription and limited capital only with human approval.
- Keep longer-term scanner/Hidden Gem/portfolio functions in product roadmap, **not as distractions from current BTC Stage-6 critical path**.

## E. Named role assignment — agents, Codex, connectors, humans

Eight **functional agent roles**, activated per task, not always-on billed workers:
1. **Orchestrator** — strict roadmap, dependencies, budget and abort conditions.
2. **Data & Provenance** — OHLCV gaps, as-of data, custodian/source documentation.
3. **Fundamentals & Feature** — macro/ETF/onchain/news/cycles, hypotheses and feature specifications; use domain subagents as needed.
4. **Model Research** — bounded classical/advanced candidates, controlled train-only fitting plans.
5. **Statistics** — matured labels, sample power, horizon-specific paired evaluation and multiplicity.
6. **Audit** — leakage, privacy, custody, security and hidden test access.
7. **Devil's Advocate** — adverse regimes, null/alternative explanations, falsification.
8. **Execution & Reporting** — deterministic run manifests, logs, CI, source/forecast receipts, plain-language status.

**Codex**, when actually connected/available: implement and review Python data pipelines, tests, feature fusion, model runner, security, GitHub workflows, deployments. It is **not** a market-data provider, independent proof custodian or scientific sign-off. **GitHub CI != Codex**. If no Codex tool is available, use available GitHub editing and tests and say explicitly that Codex did not run.

**ChatGPT (technical partner)**: select immediate roadmap task, inspect real connected sources, route to appropriate specialists/tools, implement feasible changes, validate CI, report actual evidence vs forecast, prevent distraction. It does not work autonomously between turns absent a scheduled automation or external working service.

**Founder**: final product-domain authority and approval of material spending, access changes, commercial deployment and irreversible trades; proprietary rules not posted publicly. Independent statistical or provenance witnesses remain independent external people/systems, not LLM self-signoff.

**Existing connected integrations:** GitHub (repository/Actions/PR), Render (deployment/services when authorized and actually inspected), Neon (database when required and actually inspected). **Potential** documentation/dev workflow plugins: Context7, Superpowers, OpenAI Developers (not all connected). Do not claim plugin services are wired to BTC infrastructure without verification.

**Compute:** CPU cheap/fixed deterministic tests first; bounded GPU/model-foundation experiment only if justified. Do not equate number of agent calls/models with prediction edge.

## F. Budget, safety, single-source-of-truth rules

- **User-approved combined ceiling = USD $10** for newly paid agent/API/GPU experiments. Not per call or per model. No cost without verifying account access, estimate and a reliable stop under the ceiling; report actual spending and remaining allowance only when account data support those claims. Free CI is not assumed unconditionally free under all GitHub plans.
- **Never** silently overwrite frozen 30-day 4h engine, official forecast/scores/receipts, protected model baseline, 24-family results or reserved locked OOS. No backdating, no future-label leakage, no paid unattended loops, no automated champion promotion, no autonomous financial trades.
- Work on isolated branch/PR where needed, require tests and provenance; distinguish *implemented*, *tested*, *scientifically validated*, and *deployed*.
- A successful job, two correct directions, or a low error on exposed retrospective data do not qualify as Stage-7 evidence.

### Mandatory anti-drift checkpoint for every substantial task

Before starting:
1. **North Star:** Which user outcome and official stage does this advance?
2. **Location:** We are product Phase **5/6**, scientific Stage **6/10**, until independent gate evidence changes that.
3. **One immediate objective:** Define measurable output and explicit *stop condition*; bound effort and budget. If a local bug requires > one bounded pass or blocks unrelated work, record it and return to the Stage-6 priority queue rather than abandoning other streams.
4. **Role/tool:** Which of ChatGPT, Codex, agents, GitHub, Render, Neon actually has access and is accountable?
5. **Evidence:** Produce file/PR/workflow/ledger ID, tests, quantitative result, uncertainty; call out what is not done.
6. **After-action checkpoint:** Preserve the multi-timeframe research goal and parallel fundamentals research; set next dependency; never claim future background work without a real automation.

**Status format for every user progress answer:** Current phase/stage; specific task; who actually worked; artifact/evidence; scientific status; operational blocker; verified paid spend; next action.

### Authority and preservation

This roadmap is a **navigation and coordination document**, not a new scientific preregistration and not permission to relax frozen protocols. Source-specific/frozen scientific details in Issues #71, #78, #81, #111 and their pinned artifacts take precedence for protected experiments. The founder's earlier strategy and founder master documents remain the product mission authority. Any material change to the *North Star* or horizon commitment requires explicit owner review; normal technical fixes should not silently rewrite this document.

**Most important rule:** A task is complete only when its output helps reliable, honest multi-horizon Bitcoin prediction—or prevents an identified blocker to that goal.
