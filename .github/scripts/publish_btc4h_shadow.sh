#!/usr/bin/env bash
# Persist BTC 4h evidence BEFORE attempting any older-target scores.
# Uses a separate detached worktree so the checkout of runnable code NEVER
# changes to the older data branch. Each update is append-only and fail-closed.
set -euo pipefail

phase="${1:-}"
case "$phase" in
  anchor|issue|receipt|score) ;;
  *) echo "usage: publish_btc4h_shadow.sh {anchor|issue|receipt|score}" >&2; exit 2 ;;
esac
data_branch="data/btc4h-shadow-forward"
source_dir="${GITHUB_WORKSPACE:-$PWD}/research"
work_tree="$(mktemp -d "${RUNNER_TEMP:-/tmp}/btc4h-evidence.XXXXXXXX")"
cleanup() {
  git worktree remove --force "$work_tree" >/dev/null 2>&1 || true
  rmdir "$work_tree" >/dev/null 2>&1 || true
}
trap cleanup EXIT

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
if git ls-remote --exit-code --heads origin "refs/heads/$data_branch" > /dev/null; then
  git fetch origin "refs/heads/$data_branch:refs/remotes/origin/$data_branch"
  base="origin/$data_branch"
else
  base=HEAD
fi
git worktree add --detach "$work_tree" "$base" >/dev/null
mkdir -p "$work_tree/research"

# Validate local content against the LAST PUBLISHED server branch: no row
# removal, edits or rearrangement of previous forecast/score records.
python - "$phase" "$source_dir" "$work_tree/research" <<'PY'
import json
import sys
from pathlib import Path

phase, source, destination = sys.argv[1:]
source_path = Path(source)
destination_path = Path(destination)
anchor = "btc4h_study_start_utc.txt"
forecast = "btc4h_shadow_forecasts.jsonl"
scores = "btc4h_shadow_scores.jsonl"
receipts = "btc4h_shadow_publication_receipts.jsonl"
required = source_path / anchor
if not required.is_file() or not required.read_text(encoding="utf-8").strip():
    raise SystemExit("study anchor missing; publishing forbidden")

for name in (anchor, forecast, receipts, scores):
    old = destination_path / name
    new = source_path / name
    historical = old.read_bytes() if old.exists() else b""
    proposed = new.read_bytes() if new.exists() else b""
    if name == anchor:
        if historical and historical != proposed:
            raise SystemExit("study anchor changed: fail closed")
        if not proposed.endswith(b"\n"):
            raise SystemExit("study anchor lacks newline")
    else:
        if historical and (not new.exists() or not proposed.startswith(historical)):
            raise SystemExit(f"non-append-only modification to {name}")
        if proposed and not proposed.endswith(b"\n"):
            raise SystemExit(f"truncated JSONL record in {name}")
        if proposed:
            for line in proposed.splitlines():
                try:
                    row = json.loads(line)
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise SystemExit(f"invalid JSONL row in {name}: {exc}") from exc
                if not isinstance(row, dict):
                    raise SystemExit(f"nonobject JSONL row in {name}")
        if name == forecast and phase != "issue" and historical != proposed:
            raise SystemExit("forecast ledger changed outside issue phase")
        if name == scores and phase != "score" and historical != proposed:
            raise SystemExit("score ledger changed outside score phase")
        if name == receipts and phase != "receipt" and historical != proposed:
            raise SystemExit("publication receipt changed outside receipt phase")
    if phase == "anchor" and name != anchor and historical != proposed:
        raise SystemExit("anchor phase must not modify forecasts or scores")
    if proposed and historical != proposed:
        old.parent.mkdir(parents=True, exist_ok=True)
        old.write_bytes(proposed)
PY

git -C "$work_tree" add -A -- research/
if ! git -C "$work_tree" diff --cached --quiet; then
  git -C "$work_tree" commit -m "BTC4h $phase evidence; run ${GITHUB_RUN_ID:-local}" >/dev/null
  git -C "$work_tree" push origin "HEAD:refs/heads/$data_branch"
  echo "BTC4h ${phase} evidence published to ${data_branch}" >> "${GITHUB_STEP_SUMMARY:-/dev/null}"
else
  echo "BTC4h ${phase}: no new evidence" >> "${GITHUB_STEP_SUMMARY:-/dev/null}"
fi
