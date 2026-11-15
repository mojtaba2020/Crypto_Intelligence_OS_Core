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

**Status: experimental Cloudflare Worker/GitHub Builds connected by owner; first deployment not yet verified.**

## Optional credential preflight (requires explicit owner toggle)

The token is now stored as an encrypted **runtime secret**, but Cloudflare's
successful deployment does not verify that GitHub will accept the token.

For one controlled scheduled test only, the owner can add a **runtime Variable**
named `BTC4H_TOKEN_PREFLIGHT` with value `true` in Cloudflare
Settings -> Runtime variables and secrets -> Production, *after the updated
code has deployed*. The Worker then sends **one authenticated GET** to GitHub's
Actions workflow metadata endpoint on each Cron invocation during the test.
It sends **zero** POST / workflow_dispatch requests. A successful result logs:

    {"status":"token_read_accepted","github_status":200,"dispatches":0}

A 401, 403, missing secret, or network error fails closed; do not enable live
dispatch. This only proves the credential was accepted for a **read** operation,
not that workflow dispatch or forecast delivery would succeed.

The test can run once during the next scheduled Cron period; **remove this
temporary runtime Variable immediately after** observing the result. When the
Variable is absent or anything other than `true`, disabled Workers perform
zero network calls, as before.

Keep `BTC4H_CF_ENABLED=false` and
`BTC4H_SCHEDULE_CUTOVER_CONFIRMED=false` throughout. Do NOT modify the
existing GitHub main `schedule:` or merge this experimental branch.
The preflight cannot run when either cutover gate is true.

## Connected-account deployment preflight (2026-11-15)

A Cloudflare Worker named `btc4h-free-scheduler-preflight` was created
manually, and its Builds settings were connected to the experimental branch
`experiment/cloudflare-btc4h-free-dispatch-20261115`. The visible settings
showed root directory `/`, empty build command, and deploy command:

    npx wrangler deploy --config workers/btc4h-cloudflare/wrangler.toml

This harmless documentation change starts the first Cloudflare build through
the connected repository, if its Git integration is active. Verify the
Cloudflare **Deployments / Builds** status explicitly; a GitHub commit is not
proof of Cloudflare deployment. The Worker remains gated by
`BTC4H_CF_ENABLED=false` and
`BTC4H_SCHEDULE_CUTOVER_CONFIRMED=false`, with no GitHub token configured.
Never remove these gates or touch the existing GitHub workflow schedule as
part of this preflight.

Official docs:
- https://developers.cloudflare.com/workers/configuration/cron-triggers/
- https://developers.cloudflare.com/workers/platform/limits/
- https://docs.github.com/en/rest/actions/workflows
