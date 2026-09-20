# Agent fleet pilot infrastructure

This PR implements a **local, deterministic, dry-run planner**, not an LLM agent runtime. It validates a bounded task DAG, 100 possible role IDs, 1–100 concurrency limit, supported task kinds, external-access prohibition, and emits execution waves. CI runs with read-only repository permissions, a 5-minute timeout, no API keys, and no model calls.

Run locally: `python -m unittest tests.test_agent_fleet` then `python -m scripts.agent_fleet --manifest .agent_fleet/pilot.json --dry-run`.

Next deployment gate (not included): choose and authorize a real model/runtime provider, define billing cap, secret storage and least-privilege GitHub credentials, implement a leased task queue with durable audit log, sandbox each worker and add human-approved PR-only writes. Only then activate a small measured pilot and scale toward 100 roles. No background agents are active from this PR.
