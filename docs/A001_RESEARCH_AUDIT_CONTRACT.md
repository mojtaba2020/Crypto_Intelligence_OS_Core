# A001 research audit contract (v1)

A001 is a bounded, read-only research assistant. Its successful provider smoke run does **not** establish Bitcoin forecasting skill. Do not describe the 100-agent planner as 100 running agents.

## Required evidence before any model-quality claim

1. Identify the dataset, market/pair, source, UTC timestamp convention, sampling interval, missing observations, duplicates, and data cutoff.
2. Record the forecast horizon and prediction timestamp. Features must be available **at prediction time**; exclude future candles, revised values, and full-sample normalization.
3. Use chronological train/validation/test splits, with a gap/embargo if overlapping targets require it. Tune only on training/validation; keep the final test untouched until selection is frozen.
4. Compare against a naive no-change baseline at the same timestamps and horizons. Report sample counts, MAE and/or RMSE, directional accuracy where applicable, and performance by market regime; do not infer trading profitability from forecast accuracy.
5. Record uncertainty and limitations, including nonstationarity, fees/slippage for any separate trading simulation, and the risk of repeated testing or selection bias.
6. Link reproducible input artifacts, code revision, configuration, and machine-readable metrics. If any evidence is missing, mark the result **unverified** rather than inventing numbers.

## Bounded agent output schema

- Evidence reviewed: exact repository paths and artifact identifiers, or `none supplied`.
- Checks: `pass`, `fail`, or `not assessed` for each of the six items above, with a short evidence reference.
- Highest-priority issue: one concrete, falsifiable issue, or `insufficient evidence`.
- Next experiment: one offline, reproducible test with explicit inputs and pass/fail criterion; no trading action.
- Costs: input/output token usage when the provider returns it.

## Execution and safety

Run paid API calls only through an explicitly manual workflow. Keep the agent read-only; do not expose secrets, place trades, modify production data, or claim live-market access. Review actual artifacts and tests before promoting any recommendation into a model change. The existing A001 task is a provider proof-of-execution, **not yet** an evidence-grounded audit implementing this contract.
