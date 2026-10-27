# UI hill-climbing loop

Improve one user task at a time. The score nominates a candidate; working renders and a recorded reader check decide acceptance. Existing Spine typography, palette, evidence and uncertainty labels remain authoritative.

## Setup

Node, Playwright, axe-core and browsers live on disk outside the repository:

```bash
mkdir -p ~/scratch/spine-uiloop
cd ~/scratch/spine-uiloop
npm init -y
npm i playwright @axe-core/playwright
npx playwright install firefox
cd ~/projects/spine
ln -sfn ~/scratch/spine-uiloop/node_modules tools/uiloop/node_modules
```

Firefox is the default because Chromium frame capture hangs on this host even on a blank page. `UILOOP_BROWSER=chromium` selects Chromium; baseline and candidate must use the same browser. The site still has no build step or new production dependency.

## Run and accept

1. Name the task and one change that should improve it.
2. Run `tools/uiloop/step.sh <unique-name>`. Artifacts go to `~/scratch/spine-uiloop/runs-v2` (`UILOOP_RUNS` overrides it). The first **fully rendered** run becomes the baseline. Old runs need a new baseline: the scoring contract and headline layout changed.
3. Inspect phone (390 × 844) and desktop (1440 × 900), light and dark screenshots. Missing screenshots, any empty chart, missing viewport/theme, console errors or changed headline evidence block acceptance. An intentional content change requires an explicit new baseline after checking its source; never edit metrics to bypass a gate.
4. A reader inspects the actual screenshots and page. Ask: **Where is the risk? What changed over the comparison period? Which assumptions drive the result?** Ask them to distinguish end-of-path loss from trough exposure. Record their response, the evidence used to judge it, and pass/fail. An agent's own inspection is weaker than a first-time human reader test; label who performed it.
5. Add `review.json` beside candidate metrics, using the exact metrics file's SHA-256. Each answer requires a substantive response and evidence, not just a checkbox:

```json
{
  "metricsSha256": "sha256 of metrics.json",
  "reviewer": "actual reader name and role",
  "reviewedAt": "ISO timestamp",
  "answers": {
    "risk": {"pass": true, "response": "reader's answer", "evidence": "why it agrees with the displayed values and dates"},
    "change": {"pass": true, "response": "reader's answer", "evidence": "comparison timestamps, deltas or explicit missing-history state"},
    "assumptions": {"pass": true, "response": "reader's answer", "evidence": "scenario, calibration limits and replay-book date"}
  }
}
```

6. Run `tools/uiloop/accept.sh <name>`. Only a non-worsening score, all render gates and the matching reader record return ACCEPT. An absent/incomplete review returns REVIEW, even when the numerical score improves. REJECT and REVIEW retain working files; no automatic checkout or revert can destroy unrelated edits. The accepted run points to the scored artifacts, not any later working-tree changes.
7. Record the result in LOG.md. Stop after three ideas fail, or when remaining improvements require a different user task/content decision.

## What the score measures

`score.mjs` loads the real dashboard, walks lazy charts, captures first-screen and full-page screenshots, and writes `metrics.json` with screenshot hashes. Penalties cover accessibility violations, contrast, horizontal overflow, clipped text, small controls, tiny type, long prose, layout shift, missing charts, errors, and headline answers below the first screen. Lower is better; the score is not a usability verdict. Load time is recorded rather than scored because this host is shared.

`compare.mjs` preserves headline evidence and refuses incomplete render evidence absolutely. It does not subtract persistent rendering failures as a machine artifact.

## Behavioral verification

```bash
node tools/uiloop/check-briefing.mjs
node tools/uiloop/check-workspace.mjs
node tools/uiloop/check-charts.mjs
node tools/uiloop/check-browser.mjs
.venv/bin/python -m pytest -q
```

The browser check exercises selection from the briefing, URL reload, invalid URL fallbacks, matching market labels, supplier context, first-screen answer placement, overflow, chart drawing and screenshot capture at five widths (320, 390, 768, 1440, 1920px) in both themes, including filters/sorting, shock presets, history navigation, persistent theme, copy feedback and loan-input validation. It also checks primary-data retry and optional-source fallbacks. It starts an ephemeral localhost server and closes it after the test. `UILOOP_ARTIFACTS` chooses its output folder. Optional `UILOOP_PLOTLY=/absolute/path/plotly-cartesian.min.js` serves a previously downloaded **exact 2.35.2 library** in the test to isolate CDN/network variation; disclose this when used. The production site still loads the CDN directly.

Graph-specific numerical, SVG, keyboard and shared-scale checks are in `check-charts.mjs`; `CHART_ARTIFACTS` chooses its output folder and `CHART_SKIPSHOTS=1` checks numerical geometry without new screenshots. `chart-audit.py <out-dir> [figure.png ...]` validates the local blue palette and creates full-severity linear-RGB CVD simulations using ImageMagick. See `docs/graph-review.md` for coverage and limits.
