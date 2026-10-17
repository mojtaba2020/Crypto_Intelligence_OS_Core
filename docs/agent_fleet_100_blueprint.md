# Bitcoin Intelligence OS — 100-agent fleet blueprint (design v1)

Status: **architecture proposal only**. This document does not launch agents, authorize unattended code changes, or claim that 100 workers are running. Existing GitHub Actions are deterministic workflows, not autonomous agents.

## Objective and operating principle
Design for 100 distinct agent roles in 10 squads of 10. Scale *active* workers based on measured throughput, correctness, cost and available runtime capacity; never equate agent count with forecast accuracy. The orchestration layer should dispatch bounded tasks with explicit inputs, outputs, acceptance tests and dependencies. Start with 3–5 active workers; expand to 8–12 after a successful pilot; only consider 100 concurrent workers after load, cost and conflict tests. A role definition is not a deployed worker.

## 100-role registry

### Squad 1: Data acquisition
- A001: source registry
- A002: exchange adapters
- A003: OHLCV ingest
- A004: corporate event checks
- A005: halving calendar
- A006: timestamp normalization
- A007: gap detection
- A008: duplicate detection
- A009: raw-data lineage
- A010: data freshness

### Squad 2: Data quality
- A011: schema validation
- A012: outlier triage
- A013: timezone audit
- A014: split integrity
- A015: missingness profiling
- A016: price adjustment audit
- A017: cross-source reconciliation
- A018: feature availability audit
- A019: dataset release

### Squad 3: Feature research
- A021: returns features
- A022: volatility features
- A023: volume features
- A024: trend features
- A025: cycle features
- A026: halving-distance features
- A027: market regime features
- A028: feature stability
- A029: feature ablation
- A030: feature documentation

### Squad 4: Baselines
- A031: persistence
- A032: drift baseline
- A033: seasonal baseline
- A034: rolling mean
- A035: linear regression
- A036: regularized regression
- A037: naive interval
- A038: horizon alignment
- A039: baseline calibration
- A040: baseline report

### Squad 5: Model research
- A041: tree model
- A042: boosting model
- A043: sequence model
- A044: probabilistic model
- A045: regime-conditioned model
- A046: ensemble research
- A047: hyperparameter budget
- A048: training reproducibility
- A049: model card
- A050: candidate packaging

### Squad 6: Evaluation
- A051: chronological split
- A052: purged walk-forward
- A053: locked holdout
- A054: non-overlap audit
- A055: MAE and RMSE
- A056: directional accuracy
- A057: interval coverage
- A058: regime slices
- A059: statistical uncertainty
- A060: evaluation report

### Squad 7: Risk and robustness
- A061: leakage adversary
- A062: look-ahead audit
- A063: survivorship audit
- A064: transaction-cost assumptions
- A065: stress periods
- A066: distribution shift
- A067: missing-data stress
- A068: random seed sensitivity
- A069: failure modes
- A070: risk register

### Squad 8: Engineering
- A071: CI ownership
- A072: unit tests
- A073: integration tests
- A074: workflow runtime
- A075: artifact retention
- A076: dependency security
- A077: secret scanning
- A078: branch conflict resolution
- A079: observability
- A080: release packaging

### Squad 9: Product and reporting
- A081: API contract
- A082: dashboard design
- A083: seven-horizon display
- A084: uncertainty display
- A085: data provenance UI
- A086: report automation
- A087: accessibility
- A088: user documentation
- A089: research changelog
- A090: release notes

### Squad 10: Governance and coordination
- A091: task decomposition
- A092: dependency scheduler
- A093: budget governor
- A094: concurrency governor
- A095: permission auditor
- A096: PR reviewer
- A097: independent evaluator
- A098: incident triage
- A099: human approval gate
- A100: fleet metrics

## Task contract and coordination
Every dispatched task must carry: task_id, agent_id, objective, owner squad, input artifact hashes, dataset vintage, horizon(s), dependency task IDs, writable paths, read-only paths, branch name, CPU/time/token budget, deadline, acceptance tests, output artifact paths, and escalation contact. State machine: queued → leased → running → review → accepted/rejected; expired leases return to queue. Use an idempotency key and immutable run manifest. Each code-writing worker uses an isolated worktree/branch and opens a PR; no direct writes to main. A coordinator owns the dependency DAG and conflict queue. A separate evaluator owns the locked test and cannot be overridden by model-search agents.

## Non-negotiable research controls
- Chronological splits and feature-availability timestamps; no future information in training, selection or normalization.
- Validation selects models; a genuinely untouched holdout is opened only for predeclared final evaluation. Repeated holdout peeking invalidates its independence; replace it with a new prospective test before claiming generalization.
- Report all seven horizons (1, 3, 7, 30, 90, 180, 365 days) with observation counts, MAE/RMSE, persistence baseline, uncertainty and regime-specific failures. Nonoverlapping samples where appropriate; document overlapping-label dependence otherwise.
- A better backtest is not a guarantee of future price accuracy or trading profit. No live trading, exchange credentials, production promotion, or automated financial actions in the pilot.
- Research jobs use least-privilege tokens, pinned dependencies, resource limits, and sanitized logs; secrets never enter agent prompts or artifacts.

## Rollout gates
1. **Design gate:** approve role registry, repo permissions, budget ceiling and runtime/provider choice; inventory existing workflows and protect main.
2. **Pilot (3–5 workers):** one data auditor, one model researcher, one independent evaluator, one CI/reviewer, optionally one coordinator. Run on a bounded fixture and submit separate PRs. Measure wall time, cost, failure rate, merge conflicts and reproducibility against a single-worker control.
3. **Controlled scale (8–12 workers):** parallelize only independent DAG nodes; cap simultaneous expensive training jobs; require reproducible reports and zero unreviewed production changes.
4. **Scale test (up to 100 workers):** only if measured throughput gains outweigh coordination and compute costs; increase in batches with automatic stop on budget, failure-rate, leakage, or conflict thresholds.

## Initial implementation backlog (not yet implemented)
- Define machine-readable agent registry and JSON task schema with validation tests.
- Build coordinator with bounded queue, leases, retries, per-path write locks, concurrency caps and audit log.
- Connect an explicitly authorized agent runtime/provider and GitHub App with minimum required scopes; require human approval for permissions and any external spend.
- Add dry-run simulator with synthetic tasks and failure injection before enabling real code-writing agents.
- Run a measured pilot and publish a comparison report before scaling.

## Decision rights
Workers may propose code and research artifacts within approved budgets. CI verifies tests. Independent evaluator signs off on methodology. Human owner approves runtime/provider connections, spending, branch protections, merges into main, production deployment and any trading integration. Stop the fleet on anomalous spending, repeated failures, missing provenance, suspected leakage, or unauthorized writes.
