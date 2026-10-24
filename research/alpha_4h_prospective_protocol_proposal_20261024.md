# Alpha Discovery — first prospective 4h pilot contract (PROPOSED, NOT AUTHORIZED)

**Date:** 2026-10-24. **Status:** `DRAFT_DESIGN / NO_RUN / NO_FREEZE`.
This is a concrete single-candidate experimental protocol for independent review,
**not** an approved preregistration, independent custody certificate, finished
training pipeline, or evidence of trading profitability. A1–A6 in
[Issue #81](https://github.com/mojtaba2020/Crypto_Intelligence_OS_Core/issues/81)
are independently blocked. Current formal review roles are **unfilled**.
Never portray internal code review or this document as those approvals.

## 1. Reconcile the original mathematical proposal before a single target

The candidate has exactly four regression terms: an intercept, **m** (24-hour
log-price momentum), **v** (population SD of the same 24 completed one-hour
log returns), and **m × v**. Its ablation retains intercept, m and v, and removes m × v. **Codex found
a P2 scientific confound:** with constant volatility or momentum, m × v
duplicates a base feature and gives the 3-feature ridge more coefficient
channels to share its penalty, creating a fake win over the 2-feature ablation.
Codex's second review found an additional exact **three-point additive
support** where the Taylor control was not enough: m*v was an additive
combination of m and v on the actual empirical support but the two ridge
penalties still differed. To rule out *all* empirically redundant additive
interactions in this numerical pilot, the candidate now uses a
**training-only orthogonalized interaction residual**
`r = m*v - projection_training(m*v | 1, m, v)`, computed by a rank-aware
re-orthogonalized basis. If the training residual has negligible norm,
it is pinned **exactly to zero**; the fitted candidate must then equal
the additive ablation numerically and **cannot win by redundant shrinkage**.
Projection coefficients and the zero-residual decision are frozen at
each approved refit and reused without looking at the future target.

The pilot also keeps one predeclared linearized
regularization-matched negative control as an additional stress test:
construct a third feature
`z_placebo = m × mean_training(v) + v × mean_training(m) − mean_training(m) × mean_training(v)`
and fit the *same* three-feature ridge on the same rows with this
training-only placebo replacing m × v. For constant m or constant v the
candidate and placebo inputs are identical, so an apparent ridge shrinkage
advantage cannot be credited to incremental market information. Persistence
predicts the origin reference price. Thus:

- Candidate hypothesis: the **training-residualized** portion of m × v
  supplies incremental information on a future log-price return *beyond*
  the full additive span of m and v; a zero residual is an immediate
  negative result for that fit, not a deployment success.
- Null/negative finding: no incremental gain vs the nested ablation and/or
  no gain vs persistence, the no-interaction ablation, OR the
  linearized penalty-matched placebo; reject the *interaction-specific*
  thesis even if a momentum specification is promising.
- The old V2 4h, 12h and 24h outcomes and retrospective volatility medians
  have all been examined; they cannot serve as fresh untouched confirmation.
  **No post-hoc high-volatility gate and no second candidate family**.

The single **proposed** horizon is **minimum four hours of elapsed lead**,
not a bar-aligned legacy V2 `horizon_hours=4`. Selection justification
is operational: six non-overlapping forecast origins per UTC day, relatively
quick matured feedback and limited feature requirements. This is **not**
selection based on the previously observed hourly V2 accuracy. The 4h
choice, effect size, power and evaluator still require independent prospective
signoff; until then no experiment starts.

## 2. Exact proposed clock to prevent the old shortened-horizon error

All instants UTC. Set scheduled feature-cutoff `S` at 00:00, 04:00, 08:00,
12:00, 16:00 or 20:00 UTC every day. Use the **fully completed** hourly
bar ending exactly at S (its open is S−1h) as origin reference price `P_S`.
Create the candidate forecast from the 25 consecutive hourly closes ending
at S (S−24h through S), **each with independent first-observed and vintage
receipt** no later than the actual forecast computation. Missing/late or
revised source values cannot be silently forward-filled.

Publish the exact candidate, ablation and persistence payload bytes to an
approved independently timestamped *publicly accessible* location by
`S + 15 minutes`. The external custodian must demonstrate byte-identical
first-public-access time; GitHub Actions clocks, `issued_at`, or private
signatures alone are NOT the evidence. The fixed target is the close of the
five-minute BTC-USD bar `[S+4h10m, S+4h15m)`, i.e. `T=S+4h15m`.
Consequently, `T−public_first_available >= 4h` for every eligible
forecast with publication by S+15m. Scoring is forbidden until the target's
real first-observed time AFTER T. The observed lead may be *more* than
four hours, which must be reported separately; do not market it as an
exact time-shifted 4h forward-price quote.

If publication occurs after S+15m, the slot is **MISSED_OR_LATE** for the
proposed experiment, even if the eventual target is not yet observed.
No rescheduling of that origin, opportunistic alternate target or omission
from the all-slots denominator. This hard 15m deadline is a **feasibility
risk** requiring the operator's label-blind schedule trial. Do NOT turn on a
new cron until operator/reviewer approval and cost/isolation attestation.

## 3. Candidate fitting contract requiring final signoff

For each S, the three linear/ridge research fits (interaction candidate,
nested ablation and penalty-matched placebo) must use the **same**
earlier, fully resolved labels, source vintages,
training timestamps, target convention and rolling history. Candidate:
`x=(m, v, r)` where r is the training-orthogonalized residual of m*v
after projection onto (1,m,v); ablation: `x=(m, v)`; regularization placebo:
`x=(m, v, z_placebo)`, using training-only m/v means.
The residual projection must be fit on **training inputs only**, never on
a future/test/OOS window. The numerical code currently implements this
as an internal fit of its own; real source/label eligibility remains unverified.
Fit independent standardizers
from TRAINING inputs only; never normalize on an OOS/test window. Predict
log return; convert to positive USD forecast from P_S. Ridge penalty,
window duration, refit cadence, numerical caps, feature normalization,
missing-value logic, source venue, and model-code digest are **OPEN DESIGN
FIELDS** that must be independently fixed, reviewed and hashed BEFORE
first qualifying target. The old `scripts/btc_hourly_prospective.py`
V2 features, blend search, and bar-aligned ledger are NOT the candidate.

Do not silently claim the candidate is already runnable: **no approved,
trained, independently authenticated checkpoint or model training is
supplied by this document**, and the current source availability controls
have not passed.

## 4. Single primary outcome and honest secondary diagnostics

For each scheduled S with a matured, independent observed target,
record the four forecasters' log-price absolute errors:
`L_c=|ln(P_candidate/P_T)|`,
`L_a=|ln(P_ablation/P_T)|`,
`L_r=|ln(P_regularization_placebo/P_T)|`, and
`L_p=|ln(P_S/P_T)|`.
Paired gain relative to persistence is `D_p=L_p−L_c`; paired
interaction gain against the nested ablation is `D_a=L_a−L_c`, and
against the shrinkage-matched placebo is `D_r=L_r−L_c`.
Report all three mean effects. **Scientific success requires genuine
superiority to persistence AND to BOTH controls**, rather than only winning
because a redundant ridge column relaxed a penalty;
the significance family and order must be fixed by an independent
statistics reviewer, not chosen after observing D. Direction (UP/DOWN,
exact FLAT separate), conditional accuracy, absolute USD/percentage error,
stability by calendar segment/volatility, and coverage are **secondary**
and cannot substitute for primary superiority.

At every S retain `scheduled / issued / late / missing / source-unavailable /
abstained / matured / verified / unverified`, and publish BOTH a
conditional-verified sample statistic and the all-scheduled denominator.
Without an independently reviewed missingness strategy one must **not**
assume complete-case selection is unbiased. Coverage on all expected
slots is a feasibility requirement, not evidence of alpha.

## 5. Statistics, power, independent custody — blockers with owners

- **Independent statistics reviewer:** predeclare minimum economically
  meaningful relative log-error improvement, desired power >=80%,
  confidence level, the hierarchy/multiplicity of D_p, D_a and D_r, and
  dependence-aware resampling/HAC method (including block size or lags)
  for six daily origins with overlapping 24h features. Report effective
  sample size; do not equate six slots/day with six independent samples.
  The study's N/duration is **not yet authorized**; do not make up a
  sample count or retroactively choose a stopping point.
- **External market source owner:** bind BTC-USD exchange/pair and time
  zone, hourly feature candles and five-minute targets, per-bar
  `first_observed_at`, revisions, completeness, and release delays.
  Produce a private independently verifiable custody record; if historical
  as-of claims cannot be established, say
  `HISTORICAL_AS_OF_UNVERIFIABLE` and use forward-only accepted evidence.
- **Independent publication custodian:** externally attest full identical
  candidate/ablation/persistence bytes, immutable model identity, first
  public accessibility by S+15m, and signature identity/expiry/revocation.
- **Security/operator reviewer:** enforce real file/network/credential
  isolation of reserved OOS, immutable protected ledger, GitHub workflow
  constraints, and strict zero-spend/no-trade permissions.
- **Human scientific signoff:** authenticate all those people/evidence
  rather than accepting self-named JSON review identities. Record
  `PILOT_EVIDENCE=APPROVED` only after all gates are met.

Without those **external** reports the decision is
`HISTORIC_A2=UNKNOWN; PROSPECTIVE_EVIDENCE=BLOCKED; NO_RUN`.
These are constraints, not a reason to add more synthetic test suites.

## 6. Predeclared stopping and decision boundaries — proposal only

If a fixed future approved experiment later reaches its independently
pre-registered target number of effective observations, score exactly once
at that frozen endpoint; no stopping early for wins or extending for
losses. Data/source failure or failed custody halts issuance with
`NO_RUN/BLOCKED`, preserving all lost slots. Success additionally requires
verified price lift vs persistence, incremental lift vs the non-interaction ablation **and the
regularization-matched placebo**, positive effect size of at least the signed-off threshold,
appropriate multiple-test/dependence-adjusted uncertainty, honest
denominators, and signoff. **Inconclusive** is distinct from model failure
and from success. A limited-power study MUST remain inconclusive and
cannot claim that the null is true.

**PR intent:** make it possible for an independent source owner, custodian
and scientific reviewer to accept, veto or request specific revisions of
one sharply bounded future experiment. This work does NOT operate remote
agents, train on market prices, read locked data, or issue real forecasts.
