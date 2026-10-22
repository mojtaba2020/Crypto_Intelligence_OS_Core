# GitHub Actions Pre-Step Failure Incident — 2026-09-27

## Scope

This incident is tracked separately from scientific/model validation.

## Last known good reference

- Commit: `aece6a2fce8c96bc300a71e1bf1f1a7cbbf7cc72`
- CI run: `36269784476` (#365)
- Result: SUCCESS
- Both Python 3.13 and 3.14 jobs recorded normal steps beginning with `Set up job`.

The current `.github/workflows/ci.yml` blob is identical to the blob at the last known good commit, so the present pre-step failures are not explained by a CI YAML change.

## Current failure fingerprint

Latest checked commit:
- `da3670ccd65267b3043e71980bf80a472fe2003e`

Runs:
- BTC Long-History Research #41 — failure
- BTC Hourly Model Tournament #81 — failure
- BTC Live Numeric Forecast Prototype #106 — failure
- CI #393 — failure

CI run `36290451111`:
- Python 3.13 job `108539379293`: failure, `steps = null`, `logs_url = null`
- Python 3.14 job `108539379371`: failure, `steps = null`, `logs_url = null`

Attempts to fetch logs for the same failure class have returned `BlobNotFound`.

## Interpretation

This fingerprint is **pre-runner-step infrastructure/account routing behavior**, not a test assertion or model failure:
- no `Set up job` step exists;
- no normal job log exists;
- multiple unrelated workflows fail in the same way;
- the last known good CI file is byte-identical to the current CI file.

Do not edit scientific code merely to try to turn these checks green.

## External references

- GitHub Actions billing and usage documentation:
  https://docs.github.com/en/actions/concepts/billing-and-usage
- GitHub Actions troubleshooting documentation:
  https://docs.github.com/en/actions/how-tos/troubleshoot-workflows
- Similar community-reported 2026 fingerprint (pre-step failure + BlobNotFound):
  https://github.com/orgs/community/discussions/203003

## Next infrastructure checks

When account-level visibility is available:
1. Check Actions minutes/storage usage and any spending/budget hard stop.
2. Check repository Actions policy and hosted-runner permissions.
3. If those are healthy, retry one CI job off-peak before changing workflow code.
4. If the same pre-step/no-log fingerprint persists, capture run/job IDs and escalate to GitHub Support.

## Research continuity

Scientific research must continue locally/from validated artifacts while this incident is open. Infrastructure failure must never be interpreted as model PASS/FAIL evidence.
