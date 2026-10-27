# UI loop log

One row per step. Penalty is from `score.mjs`; lower is better.

Host note (2026-10-26): headless Chromium on the dev box could not capture frames, so no screenshots were taken and no chart drew. Every run carries the same `emptyCharts` 140, which cancels out in comparisons. Chart legibility and the tie-break visual review were not checked in these runs.

| Step | Change | Penalty | Verdict |
|---|---|---|---|
| 01 | Baseline | 234 | - |
| 02 | Cap prose at 72ch (`p:not(.banner), dd`) | 215 | ACCEPT, longLines -19 |
| 03 | Coinbase badge 0.7rem to 0.75rem (12px) | 195 | ACCEPT, tinyText -20 |
| 04 | Light-mode `--muted`, `--ok`, `--warn` darkened to AA on cards, same hue | 183 | ACCEPT, contrast -12 |
| 05 | Scrollable tables get `tabindex="0"`, `role="region"` and a name | 173 | ACCEPT, axe -10 |
| 06 | Summaries and toggles reach 24px targets | 149 | ACCEPT, smallTargets -24 |
| 07 | Scorer: `foldMiss` scaled by distance below the fold; best re-scored | see below | rebase |
| 07 | (rebase result) | 144.08 | - |
| 08 | Phone: h1 1.375rem, tighter tile padding and gap | 143.52 | ACCEPT, foldMiss -0.56 |
| 09 | Phone: hide the "Now" lede; the tiles name themselves | 142.96 | ACCEPT, foldMiss -0.56 |
| 10 | Phone: four book figures in one row | 142.50 | ACCEPT by score, then reverted by hand: labels such as COLLATERAL overflowed 59px boxes. Scorer gained `clipped`. |
| 11 | Scorer: add `clipped`; best (step 09) re-scored | 142.96 | rebase |
| 12 | Retry of step 10 under the new scorer | 154.50 | REJECT, clipped +12 (proves the gate) |
| 13 | Phone: hero 2rem, nav links 10px padding | 142.84 | ACCEPT, foldMiss -0.12 |
| 14 | Phone: tighter glossary margin and "Now" top padding | 142.68 | ACCEPT, foldMiss -0.16 |

## Where the climb stopped

Every measured defect is now zero except two:

- `foldMiss` 1.84: on a 390 × 844 phone the worst-path tile starts at 982 px, 180 px below the first screen. The remaining space is evidence (book figures, the per-market distance list, the colour caveat). Closing it needs a content decision, such as a one-line summary of all three answers under the title. It is not a spacing fix.
- `longLines` 1: the stale-data banner runs 139 characters wide on desktop. It is a full-bleed alert and shows only when data is stale.

Steps 08 to 14 each gained under 0.6. The next useful step is the content decision above, followed by a visual review on a host that can take screenshots.

## 2026-10-26 — risk briefing and acceptance contract v2

Added a compact first-screen risk briefing, snapshot-anchored daily comparisons, model confidence/validation labels and one shared market selection with URL state. Existing detailed figures remain available. Capital sensitivity and warning time now use the selected market rather than retaining cbBTC/86% assumptions. Missing chart-library downloads retain the data-table alternative.

Replaced the previous constant-render-failure allowance with hard chart/screenshot gates and mandatory reader evidence for candidate acceptance. Rejection no longer rewrites the working tree. Firefox resolves this host's Chromium frame-capture limitation. Final automated penalty is 1.0 (wide desktop stale-banner line length); all four runs render every chart, capture screenshots and have no axe/contrast/overflow/error failures. This is a new schema/baseline and is not a numerical comparison with the old 142.68 score.

Python: 28 passed. Briefing/gate checks: 20 assertions passed. Real browser: four viewport/theme combinations plus missing history, replay and chart-library states passed. Reader validation remains pending; see `docs/ui-briefing-review.md` and saved ignored artifacts.

## 2026-10-26 — workstation-1

Audience confirmed: risk monitoring and market investigation. Added persistent context, a nine-market watchlist with attention filter/sorting, an exact-sample shock inspector, URL history, theme preference, copy feedback and primary-data retry. Preserved the established blue identity and all evidence/data.

One independent visual-critic review and one repair batch resolved the phone replay comparison, theme truncation, capacity reconciliation and speculative empty-state copy, along with measured accessible-label/landmark/contrast/target defects. Final critic: 4/5 in eight categories, no remaining material concern. Reader responses explicitly identify an agent with two-round familiarity; no human study claimed.

Final penalty 0.0; 28 Python tests passed; workspace checks covered45 exact samples plus URL/sort/filter boundaries. Ten width/theme behavior contexts and four source-failure states passed. Compare against the prior valid1.0 baseline returned ACCEPT, with no render/evidence/review failures. See `docs/ui-workstation-review.md` for exact hashed artifacts and limitations.
