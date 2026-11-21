# Stage 6: Bitcoin multi-horizon fundamentals fusion — parallel research lane

Status: **RESEARCH DESIGN / SCHEMA-ONLY / NO TRAINING OR PROMOTION AUTHORIZED**.
Linked to Issues #71 (scientific stage), #78 (13-horizon charter), #81
(independent source-availability custody) and #116 (BTC Intelligence V2).
This is a **parallel subtrack within the existing roadmap**, not a new roadmap
or a modification of the live BTC4h rolling or protected 30-day studies.

## Study question

Does adding timestamp-authenticated, actually available **fundamental,
economic, on-chain, derivative, ETF and narrative** observations improve BTC/USD
price and direction forecasts over a separately maintained price/volume model
and Persistence, on the same forecast issue calendar and exact target horizons?

Do not assume one driver always raises or lowers BTC. The relationship should be
learned on training-only observations, with uncertainty. Narrative sentiment is
not a numerical movement target. Correlation is not proof of causation.

## Candidate inputs, not a declaration of provider access

- Bitcoin-specific: past BTC price/volume/momentum, halving elapsed time,
  issued supply, network hashrate, active addresses, miners, exchange
  netflows, available market liquidity and reported ecosystem activity.
- Economy: US CPI surprise (requires independently timestamped **consensus
  expectation vintage**), payroll surprise (ditto), FOMC policy outcomes,
  real yield, US dollar strength and global liquidity.
- BTC financial markets: spot ETF **net reported flows**, futures funding,
  open interest, option skew.
- Narrative: separately witnessed publications and classification time;
  uncertainty and independent publisher/source verification required.
- Project ecosystem: developer activity, security events, protocol changes.
  For other tokens' FDV/unlocks, use only as a distinct **cross-asset**
  hypothesis with permitted, causal historical availability. Do not
  assume BTC has normal venture-token unlock schedules.

Potential legitimate data-source families to vet: Federal Reserve ALFRED
realtime/vintages for macro (day-level vintage alone does not establish
minute-of-release); official announcements and historical pre-release
consensus snapshots; ETF issuer/fund publication logs; audited exchange
feeds; independently versioned Bitcoin on-chain providers. Reconstructed
historical events cannot be mislabeled as first-live observed data.

### What this PR actually implements

`scripts/btc_v2_fundamental_features.py` defines a versioned candidate-metric
registry, validates strictly timestamped numeric observations, requires
source/version/units, gates known-by-issue data, and surfaces every absent
metric as **null plus explicit missingness** (never zero). It exports a
label-free fusion snapshot of technical, news and fundamental features.

This is deliberately not a live feature pipeline or a trained model:
`train_eligible=false` and `independently_verified=false` remain explicit.
A fake 2020 `first_seen` inserted into a 2026 API result can pass purely
syntactic timestamp validation: an independent custody system is required
to verify truth. Snapshot code cannot supply such evidence.

## Training and experiment when source gates are satisfied

1. Register each source's venue/metric, units, observation-window semantics,
   publication-time, first-collection evidence, historical revision policy,
   license, and allowed missingness/freshness; review source provenance.
2. Align every source observation to the **forecast issue cutoff** (not
   the economic observation date or ETF session date). For example,
   a daily US ETF number published after stock-market close is *not*
   available in an earlier four-hour BTC prediction. No post-event consensus
   surprise may use later revised expectations. Use UTC internally; present
   user-facing schedules in Houston local time.
3. Make same-origin, label-blind feature tables for approved development
   history; data unknown at cutoff stay null + missing flag. Fit scalers,
   imputers, encoders and calibrators **inside train folds only**.
4. Separate comparator cohorts with fixed model family and budget:
   (A) Persistence, (B) price/volume-only, (C) price/volume + macro,
   (D) price/volume + ETF/derivatives, (E) price/volume + on-chain,
   (F) price/volume + narrative, (G) predeclared full fusion.
   Keep each candidate's feature availability and forecast coverage visible.
   Do not permit a post-hoc winner-picked feature shopping spree.
5. Per horizon, use purged rolling-origin evaluation with matured labels,
   same target clock and baseline reference price, feature/version SHA,
   prospective issuance receipt, and non-overlapping training/holdout leakage
   guards. Respect Stage 6 0/24 NO-GO and reserved locked-test prohibitions.
6. Compare paired absolute log errors, directional correctness,
   abstentions, calibration, uncertainty intervals, and results by
   Bull/Bear/Sideways and volatility regime. Use dependence-aware
   uncertainty and predeclared multiplicity correction across 13 horizons;
   require independent scientific review and fresh prospective verification
   before any model freeze.

## No-go conditions

Missing authentic first-seen timing; license ambiguity; retrospective
vintages masquerading as actual issue-time values; unverified consensus
surprise; train/test transforms fit globally; any protected OOS leakage;
tiny dependent samples; selected "winner" based on the same exposed
October outcomes; missing source coverage hidden; any impact to the frozen
BTC4h experiment; trading, paid-provider enrollment or automatic promotion.

**Next actual blocking gate:** name/verify independent source-data custodian
and raw forecast witness (Issue #81), then propose source-specific
feasibility and fold counts without looking at reserved labels. No
historical/full-fusion model is trained or deployed by this document.
