#!/usr/bin/env bash
# Confirm Git's actual remote content before recording a first-party receipt.
# This does NOT prove a GitHub server timestamp or independent candle vintage.
set -euo pipefail

data_branch="data/btc4h-shadow-forward"
forecast="research/btc4h_shadow_forecasts.jsonl"
receipts="research/btc4h_shadow_publication_receipts.jsonl"

# A skipped issue must not manufacture a publication claim.
set +e
python - "$forecast" "$receipts" <<'PY'
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

issues, receipts = [Path(x) for x in sys.argv[1:]]
if not issues.exists() or not issues.read_text(encoding="utf-8").strip():
    raise SystemExit(10)
last = json.loads(issues.read_text(encoding="utf-8").splitlines()[-1])
known = [
    json.loads(line)["origin_utc"]
    for line in receipts.read_text(encoding="utf-8").splitlines()
    if line.strip()
] if receipts.exists() else []
if last["origin_utc"] in known:
    raise SystemExit(10)
target = datetime.fromisoformat(last["target_5m_close_utc"].replace("Z", "+00:00"))
if datetime.now(UTC) >= target:
    raise SystemExit("UNCONFIRMED_PREVIOUS_ISSUE: target already closed")
PY
check_status=$?
set -e
case "$check_status" in
  0) ;;
  10) echo "No unconfirmed pre-target BTC4h issue to record."; exit 0 ;;
  *) echo "Invalid or expired BTC4h publication receipt attempt" >&2; exit "$check_status" ;;
esac

remote_sha="$(git ls-remote origin "refs/heads/$data_branch" | awk '{print $1}')"
if [ "${#remote_sha}" -ne 40 ]; then
  echo "No remote issue commit found" >&2
  exit 1
fi
git fetch origin "refs/heads/$data_branch:refs/remotes/origin/$data_branch"
fetched_sha="$(git rev-parse "refs/remotes/origin/$data_branch")"
if [ "$remote_sha" != "$fetched_sha" ]; then
  echo "Remote ref changed while verifying publication" >&2
  exit 1
fi
verified="$(mktemp "${RUNNER_TEMP:-/tmp}/btc4h-remote-issue.XXXXXXXX")"
trap 'rm -f "$verified"' EXIT
git show "$fetched_sha:$forecast" > "$verified"
if ! cmp -s "$verified" "$forecast"; then
  echo "Remote published forecast bytes disagree with run's original ledger" >&2
  exit 1
fi

# The timestamp is sampled only AFTER verifying remote SHA + complete bytes.
python -m scripts.btc4h_publication_receipts \
  --issues "$forecast" \
  --receipts "$receipts" \
  --remote-sha "$fetched_sha" \
  --run-id "${GITHUB_RUN_ID:-local}"
bash .github/scripts/publish_btc4h_shadow.sh receipt
