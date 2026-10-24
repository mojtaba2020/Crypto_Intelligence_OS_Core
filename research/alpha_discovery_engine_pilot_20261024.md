# Alpha Discovery Engine — falsification-first pilot (2026-10-24)

**Research design only. Not a fitted model, an automatic agent service, a scientific result, a funded experiment, or a live forecast.**

## What changed from the old Stage 6

The historical V3 family has **0/24 Freeze-ready**, and the existing hourly V2 public
ledger has shown no independently verified price/direction edge. More CI,
synthetic mocks, or simulated agent slots are not an acceptable substitute
for predictive evidence. The old agent_fleet.py knows how to order up to
100 *simulated* worker IDs; it is NOT a remote agent engine.

The new **Alpha Discovery Engine** starts with one falsifiable hypothesis
and a negative control, not 100 fit requests. Its deterministic decision
kernel requires three different review roles:

1. **Mechanism challenge:** Is the claimed signal available before the
   prediction and independent of the label?
2. **Adversarial falsifier:** Can a placebo/alternative explanation reproduce
   the effect, or is it due to selection or missing origins?
3. **Statistics challenge:** Are baseline, primary price metric, uncertainty,
   sample power, multiplicity, stop rules and overlap handling sound?

A VETO kills the design regardless of other approvals. Duplicate reviewer
identifiers are refused; distinct names are NOT authenticated identities.

## Concrete first hypothesis

The sole design in research/alpha_discovery_pilot_20261024.json is the
**past-only trend × realized-volatility interaction**. Hypothesis: that
interaction may contain incremental BTC log-price information in
prespecified market regimes. Falsification requires the same new future
full-elapsed target schedule and an identically complex placebo assembled
using only legitimate past training data, with persistence as baseline.
Price error is primary; direction/coverage secondary.
This is a *hypothesis*, not an empirical finding.

Prior V3/hourly V2 outcomes have been seen; the design explicitly declares
ALREADY_EXPOSED. Forecast horizon stays UNDECIDED until independently
reviewed prospective preregistration. Do not choose the most flattering old
bar-aligned 12h or 4h score as a new independent winner.

## Run price-blind deterministic design kernel

    python -m scripts.alpha_discovery_engine --manifest research/alpha_discovery_pilot_20261024.json

Expected report: CHALLENGE_PENDING until review artifacts exist; VETO / REVISE /
DESIGN_REVIEWED_ONLY for valid submissions; selected_winner=null,
real_agents_dispatched=0, external_calls=0, external_cost_usd=0,
scientific_authorization=NO_RUN, stage7_freeze_authorized=false.

The available Codex code review integration can critique this new draft,
but is not wired into a remotely executing research/model tournament. No
agent receives reserved OOS information merely to produce an opinion.

## Exit to a REAL future experiment (NOT implemented)

A separate operator and independent reviewer must first clear
[Issue #81](https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/issues/81)
A1–A6: authenticated historical publication/revision vintages, external
immutable forecast-byte first-publication time, real runner/reserved-data
isolation, pinned code/cost permissions and independent signoff.
Then preregister exactly one horizon, schedule, baseline, placebo, candidate,
metric, acceptable effect, statistical power and outcome-blind stopping.
The first test requires fresh genuine prospective evidence and the full
scheduled denominator, not only successfully issued rows. Without independent
provenance: NO_RUN, not a synthetic pass.

**Production/workflow costs:** no nightly/cron changes, market API, trading,
actual fitting, main merge, protected OOS or paid agent deployment. Only
ordinary PR CI and read-only Codex critique if requested. Keep Draft.
