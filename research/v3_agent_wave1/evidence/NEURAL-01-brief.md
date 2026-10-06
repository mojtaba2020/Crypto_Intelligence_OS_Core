# NEURAL-01 — Neural Time-Series Agent
Scope: development_validation_only.

Mission: specify exactly one bounded neural challenger suitable for the available Challenger V3 walk-forward setting. Keep architecture and search space intentionally small. All preprocessing and fitting must occur inside each training fold, with deterministic seeds and the same causal inputs/evaluation origins used by comparable classical challengers.

Explain why the model has a credible inductive bias for this data regime and define a cheap rejection test before any broad training campaign.

Forbidden: broad architecture search, Fresh Locked OOS, V2 locked outcomes for tuning, prospective outcomes, promotion/Freeze authorization.
