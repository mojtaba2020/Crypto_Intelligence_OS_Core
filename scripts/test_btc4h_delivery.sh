#!/usr/bin/env bash
# Offline tests of adapter against frozen dependencies; never reads/writes data branches.
set -euo pipefail
root="$(git rev-parse --show-toplevel)"
pinned=9de38d2c30c892d6e7ef3d65a0ee5a6507f77dc9
python_bin="${BTC4H_TEST_PYTHON:-python}"
python_bin="$(command -v "$python_bin")"
tmp="$(mktemp -d)"
trap 'git -C "$root" worktree remove --force "$tmp" >/dev/null 2>&1 || true' EXIT
git cat-file -e "$pinned^{commit}"
git worktree add --detach "$tmp" "$pinned" >/dev/null
cp "$root"/scripts/btc4h_{continuous_forward,delivery_integrity}.py "$tmp/scripts/"
cp -r "$root/research_tests" "$tmp/research_tests"
cd "$tmp"
PYTHONPATH="$tmp/src:$tmp" "$python_bin" -m pytest -q research_tests
