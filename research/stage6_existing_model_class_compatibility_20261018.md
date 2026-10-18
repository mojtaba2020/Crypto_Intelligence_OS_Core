# Read-only compatibility audit of existing research model classes

**2026-10-18 · DRAFT, SYNTHETIC OBJECTS ONLY · NO_RUN / NO_FREEZE.** Stacked strictly on Draft PR #95 head `597cd0343754214e5be6edcbb239ca5858d1fe47`; no model fitting, real checkpoint deserialization or workflow edits.

## Why

The public `main` Git tree contains source definitions of `ai_forecasting.TrainedModel` and `hybrid_forecasting.HybridModel`, but no identifiable committed *fitted model checkpoint* was found in the recursive tree listing. Their current trainers consume **consecutive DAILY observations** and integer `horizon_days` labels, not native hour/ISO-week/month target calendars. The Python classes also do NOT encode a cryptographically pinned serialized artifact, source venue, model-creation timestamp, independent signature, first-public availability or independent training-label custody. Thus a structurally valid dataclass does **not** establish a trained, authorized or reproducible model.

## Engineering diagnostic

`scripts/stage6_existing_model_metadata_audit.py` accepts ONLY exact instances of the two existing research-model Python classes, supplied by caller in memory; examines their *public metadata* but never calls `train`, `predict`, `_fit`, `_estimate`, reads prices, serializes weights or interacts with disk/network:

- Validate that the original model has a positive integer `horizon_days`, positive `train_examples`, a genuine `date` last training target, finite and bounded coefficients, and the class-specific dimension/group constraints. Existing linear baseline requires 3 coefficients; Hybrid has 5/8/10/12 feature dimensions, 1 extra intercept weight, finite scaling and blend 0..1.
- Diagnose each of the exact 13 user-requested horizon IDs. Only **1d, 2d or 3d** may qualify for mere *DAILY SHAPE compatibility*, and only when the class's horizon_days matches, its reported training-target day is **strictly before** the synthetic UTC daily forecast origin date, and the origin is canonical midnight.
- Explicitly do **not** translate `horizon_days=7` into native `1w` Monday-anchored target, nor 30 days into a calendar month, nor daily targets into any hourly target. Their target/calendar and training-feature semantics are not identical.
- Produce one of `DAILY_SHAPE_COMPATIBLE_BUT_UNVERIFIED` or `INCOMPATIBLE_OR_UNRESOLVED_MODEL_METADATA`, with precisely named reasons and all **model execution / training lineage / bytes / signature / custody / vintage / performance authorizations FALSE**. Full 13-horizon matrix must show **at most one** compatible daily horizon per caller model, never 13.

## Security/science boundaries

A caller can instantiate the classes manually with invented coefficients and dates; passing the diagnostic is **NOT trained-model proof**, never an immutable checkpoint identifier, model issuer provenance, first-publication or training target-resolution evidence, empirical interval coverage, predictive accuracy or research approval. Absence of identifiable committed checkpoints on main does NOT prove a model artifact is absent from external private storage. No protected OOS or real data is accessed.

Any eventual real import requires a **separate authorized checkpoint schema** carrying actual signed/pinned bytes, feature mapping, exact target horizon/calendar semantics, model code hash, independent training/data vintage receipt, verified labels available at creation, license and actual runtime isolation. Those independent A1–A6 are outstanding under Issue #81. Stage-6 remains **NO-GO / NO_RUN / NO_FREEZE**, V3 0/24 freeze-ready, all PRs Draft/unmerged.

Acceptance: exact-head full CI Python3.13/3.14, Ruff/mypy and independent Codex adversarial software review. No merge.
