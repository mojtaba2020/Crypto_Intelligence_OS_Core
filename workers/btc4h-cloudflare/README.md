# BTC4h free scheduler alternative — experimental ONLY

This standalone Cloudflare Worker is a **disabled-by-default dispatcher** for the
existing BTC/USD 4h rolling research GitHub Action. It does not run Python,
calculate or publish forecasts, or place trades. It never touches the separate
formal 30-day study or the CMT project.

## Design

Cloudflare Workers Free Cron Trigger (UTC) -> GitHub workflow_dispatch for the
already-existing btc4h_continuous.yml -> existing GitHub Actions computation and
append-only research evidence.

Runs would be requested at UTC hours 00,04,08,12,16,20, at minutes 08,10,12,14
(issue retries) and 20 (score). That is 30 dispatch attempts/day. The Worker
uses only one Cron Trigger, within Workers Free's five-trigger limit.

**Important:** GitHub Actions job startup can still be delayed. This alternative
removes Render fees but has **not** been demonstrated to solve the strict
S+10..15 minute deadline. A GitHub dispatch response is NOT a forecast receipt,
and a missed issue is never backfilled.

## Proved locally / on PR

Node 22+ offline tests (no token, account, market data, or network needed):

    node --test workers/btc4h-cloudflare/test/index.test.mjs

The read-only GitHub Actions PR preflight executes the same mocked tests.
It cannot publish forecast data or modify other services.

## Fail-closed guards

1. BTC4H_CF_ENABLED=false by default. A disabled invocation performs no network calls.
2. BTC4H_SCHEDULE_CUTOVER_CONFIRMED=false is a separate gate.
3. BTC4H_GITHUB_ACTIONS_TOKEN must exist as an encrypted Worker secret; never
   paste it into repository code. Restrict the token to this repo and Actions:write.
4. Each enabled attempt downloads the live main workflow and REFUSES dispatch if
   the existing GitHub schedule is still present. Any inspection error blocks.
5. A strict UTC scheduled-time vs real-time check rejects delayed attempts.
6. Public HTTP requests return 404: no public trigger endpoint.
7. Only one GitHub Actions request with issue or score is dispatched per trigger,
   and only the existing workflow is targeted. Existing per-origin ledger safety
   remains the writer-of-record.

## Not yet done; separate authorization required before live activation

- Create/connect a Cloudflare Workers account (the current conversation has no
  Cloudflare deployment connector) and deploy this inert Worker from its directory.
- Dry-run the scheduled handler locally using Wrangler and mock network calls.
- In a separate reviewed change, remove only the rolling workflow's competing
  schedule on main while preserving workflow_dispatch, formal study and evidence.
- Store a fine-grained Actions:write GitHub token as a Cloudflare encrypted secret.
- Then separately authorize BOTH enabling flags; verify live dispatch, actual
  startup, a valid >=240-minute forecast horizon, remote publication receipt, and
  later realized score. Restore GitHub schedule on rollback, never overlap writers.

**Status: code + offline preflight only; Cloudflare not provisioned.**

Official docs:
- https://developers.cloudflare.com/workers/configuration/cron-triggers/
- https://developers.cloudflare.com/workers/platform/limits/
- https://docs.github.com/en/rest/actions/workflows
