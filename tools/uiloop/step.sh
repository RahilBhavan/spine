#!/usr/bin/env bash
# Score a candidate without overwriting the user's working tree on rejection.
set -euo pipefail
cd "$(dirname "$0")/../.."
RUNS=${UILOOP_RUNS:-$HOME/scratch/spine-uiloop/runs-v2}
name=${1:?Usage: step.sh <new-run-name>}
[[ "$name" =~ ^[a-zA-Z0-9][a-zA-Z0-9_-]*$ && "$name" != best ]] || { echo 'Use a simple, unique run name (not best).'; exit 1; }
mkdir -p "$RUNS"
[ ! -e "$RUNS/$name" ] || { echo 'Run already exists; choose a new name.'; exit 1; }
node tools/uiloop/score.mjs "$RUNS/$name" > "$RUNS/$name.log" 2>&1
if [ ! -e "$RUNS/best" ]; then
  node --input-type=module - "$RUNS/$name" <<'JS'
import { readFileSync } from 'node:fs';
import { renderFailures } from './tools/uiloop/gates.mjs';
const dir = process.argv[2];
const failures = renderFailures(JSON.parse(readFileSync(dir + '/metrics.json')), dir);
if (failures.length) { console.error(failures.join('\n')); process.exit(1); }
JS
  ln -s "$RUNS/$name" "$RUNS/best"
  git diff -- site > "$RUNS/accepted.patch"
  echo 'BASELINE: renders verified; future candidates also require reader review.'
  exit 0
fi
node tools/uiloop/compare.mjs "$RUNS/best" "$RUNS/$name" | tee "$RUNS/$name.verdict"
echo 'Working files retained. After adding review.json, use accept.sh to compare again and promote.'
