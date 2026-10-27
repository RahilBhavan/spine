#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
RUNS=${UILOOP_RUNS:-$HOME/scratch/spine-uiloop/runs-v2}
name=${1:?Usage: accept.sh <run-name>}
[[ "$name" =~ ^[a-zA-Z0-9][a-zA-Z0-9_-]*$ && "$name" != best ]] || exit 1
node tools/uiloop/compare.mjs "$RUNS/best" "$RUNS/$name" | tee "$RUNS/$name.verdict"
if rg -q '"verdict": "ACCEPT"' "$RUNS/$name.verdict"; then
  ln -sfn "$RUNS/$name" "$RUNS/best"
  echo 'Accepted scored artifacts. Current working files were not modified.'
fi
