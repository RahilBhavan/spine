# Spine risk briefing — 2026-10-26

Historical first-pass record. Superseded by the [workstation review](ui-workstation-review.md), including the completed named-agent visual/reader review. The pending status below describes the earlier pass.

Implemented locally. Not published. **Design review pending a first-time reader check.**

## Design and behavior

Reader: someone checking Coinbase's Morpho loan book who needs to identify the risk, understand its movement and inspect its assumptions.

The first screen gives the observed total borrow, selected market's modeled capacity threshold, and largest end-of-path replay loss. Trough exposure is shown separately, with its own path label. Existing book details remain in a disclosure. The daily comparison comes before that disclosure so it is immediately reachable after the briefing.

Spine's existing system remains authoritative: system fonts, blue links, light/dark semantic tokens, 15px body, 8px spacing rhythm. This is a refinement of the established dashboard, not a migration to the personal website's charcoal/yellow identity. New answer rows use rules, plain text and native links/selects. No decorative motion or new production dependency.

The comparison uses the snapshot nearest 24 hours before `summary.generated_at`, within 6 hours of that target. It never compares a stale book against the reader's wall clock or uses a future row. Both timestamps appear. Missing baselines produce an unavailable state. Changes in distance use percentage points; a null distance (>70% without a crossing) is not treated as a numeric 70% for subtraction. Capacity changes are labeled as estimates reflecting both depth and model assumptions, not as raw observed depth changes.

Market selection is shared by the briefing, daily comparison, book, liquidation charts, heatmap, capital sensitivity, warning time and supplier exposure. The old all-market breakdown explicitly retains its cbBTC reference example. Market/scenario/metric survive URL reload; loan-address writes preserve those parameters. Invalid URL values fall back to known defaults. Existing `#cbXRP` links still work. The heatmap's selected scenario is distinguished from the explicitly AB baseline/replay and supplier comparisons.

Confidence copy distinguishes observations, estimates and the hypothetical Coinbase backstop. Replay-book and run dates are explicit. Held-out calibration ratios come from the dataset and are described as validation results, not loss confidence intervals. End-of-path loss and trough exposure must not be added.

## Verification

- `node tools/uiloop/check-briefing.mjs`: 20 assertions covering historical baseline selection, missing history, null distances, signed deltas, worst-path selection and hard acceptance/review gates.
- `.venv/bin/python -m pytest -q`: 28 passed.
- `node tools/uiloop/check-browser.mjs`: actual Firefox UI exercised at 390×844 and 1440×900 in light/dark, including market selection, URL reload/fallbacks, matching selected-market controls and supplier labels, first-screen placement, overflow, chart drawing and screenshots. Keyboard focus/selection and explicit history/replay/CDN failure states are also exercised.
- The behavior run used a local copy of the exact production Plotly 2.35.2 library to isolate CDN variation. The scoring run used the production CDN directly and rendered every chart in all four contexts.
- Final score: **1.0**, entirely the desktop stale-banner line-length heuristic. No axe violations, contrast failures, overflow, clipping, small targets, tiny text, below-fold headline answers, empty charts, console/page errors or measured layout shift in the four scored contexts. This is the scoped automated result, not a claim of complete WCAG compliance.
- Chromium frame capture still hangs on a blank test page on this host. Firefox frame capture works and is now the scorer default. Safari, Windows and native mobile browsers were not exercised.
- Inspected first-screen phone/desktop renders in light/dark. Color is not required to read the new answer rows or daily table; all changes have signed text and named measures. The new numeric view uses text/table values, so no length/area encodings or Lie Factor apply. Existing chart scales remain as before; this is not a new audit of every prior chart's design.

## Exact artifacts

Saved locally in [`.artifacts/ui-briefing-2026-10-26/`](../.artifacts/ui-briefing-2026-10-26/), ignored by Git to keep generated screenshots out of source changes:

- [Metrics and screenshot/source SHA-256 hashes](../.artifacts/ui-briefing-2026-10-26/metrics.json)
- [Phone light](../.artifacts/ui-briefing-2026-10-26/phone-light-fold.png) and [phone dark](../.artifacts/ui-briefing-2026-10-26/phone-dark-fold.png)
- [Desktop light](../.artifacts/ui-briefing-2026-10-26/desktop-light-fold.png) and [desktop dark](../.artifacts/ui-briefing-2026-10-26/desktop-dark-fold.png)
- Full-page PNGs and element captures alongside these files.

The source hashes in metrics identify the site revision that produced these captures. No external post or social image was created; post-to-image agreement is not applicable.

## Acceptance boundary

The updated loop refuses missing charts/screenshots absolutely, even when the same failure was present in the baseline. Screenshot hashes bind the evidence to the run. Every candidate also needs a named, dated reader record tied to the metrics hash, with responses/evidence for risk, change and assumptions. No reader record has been fabricated for this change. Comparing the final run to itself returns **REVIEW**, with no render failures and a missing reader-review record.

[Rahil Design](/home/rahil/.codex/skills/rahil-design/SKILL.md) requires: “until a named reviewer passes the exact bytes, it is design review pending.” Agent inspection and automated checks do not establish a first-time human reader's comprehension. The work remains local and reviewable under that boundary.
