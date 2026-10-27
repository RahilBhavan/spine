# Spine blue graph review — 2026-10-26

Graph implementation and independent agent visual review are complete. **Human reader-check response and publication approval are not claimed.** No deployment was performed.

## Authority and scope

The user requested the graph work and explicitly chose **blue instead of yellow**. This local override is recorded in [DESIGN.md](../DESIGN.md), graph extension `spine-blue-graphs-1`. No global skill/token palette was changed. Present Data, Tufte Graphics, dataviz, Rahil Design and the shared design workflow guided the changes; the established analytical-product identity remains authoritative.

All seven dashboard graphs and both writeup graphs were inspected and refined. The writeup renderer now emits the same shared graph stylesheet and a working replay-measure toggle. The generated HTML exactly matches `python -m spine.render_writeup --stdout` by SHA-256.

## Comparisons and chart decisions

| Figure | Reader's comparison | Changes and integrity |
|---|---|---|
| LTV distribution | Where is borrowing concentrated relative to liquidation thresholds? | Largest bin blue, other bins gray; explicit threshold labels; linear bars start at zero. Log view uses dots, not log-length bars; zero bins remain in the table. Whole-market HF statistic is labeled as such when wallets are filtered. |
| Liquidatable debt | When does debt exceed stressed selling capacity? | Blue debt line, dashed gray bad-debt subset, dotted dark capacity; first sampled crossing labeled. Removed competing raw venue lines, retaining their numeric reconciliation below. The filtered wallet subset does not inherit a false whole-market crossing. Log axis and omitted zeros are explicit; no log-area fill. |
| Liquidation history | Which day had the highest repayment? | Blue peak, neutral context, zero baseline and direct amount label. Range is anchored to the saved snapshot rather than today's clock. Removed text promising nonexistent named-event annotations. |
| Snapshot trend | How did three measures change over time? | Three small multiples share time, not mixed value axes. Each panel names units and latest value; zero-based value axes; gaps at no sampled threshold crossing are explained. Reduced repeated marker ink. |
| Crash matrix | How do LLTV and historical path affect the selected measure? | Phone transpose, 12px labels, blue scale fixed across scenario changes for a market/measure; all amounts printed; missing runs distinct from zero; dynamic measure title and dated replay scope. |
| Capital matrix | How does the selected measure differ across daily capital assumptions? | Same dollar scale as crash matrix. Capital levels are labeled categories, including hypothetical unlimited; fractional multiples are preserved rather than rounded into duplicate categories. |
| Warning time | Which path gives the shortest median warning? | Horizontal bars, zero-based linear hours axis, direct duration labels, shortest available warning blue. No median and Not run are distinct. Caption states the positions covered by the median. |

Figure choice follows question and shape: distributions/time series show concentration or movement; warning bars compare duration; printed-value matrices support row/column lookup. The new dark/blue lines have dash-pattern and textual redundancy. No estimates are presented as observed loss or forecasts.

## Numerical and behavior verification

- **28 Python tests passed.** Modeling and source data were not changed.
- **20 briefing/gate checks passed**, plus workspace source/boundary checks covering45 exact shock samples.
- `check-charts.mjs` passed in **390px/1440px × light/dark**: exact source arrays, zero baselines, log-dot mode, fixed scenario color scale, correct heatmap transpose and source matrix, all SVG text≥12px, no graph text clipped outside its figure, keyboard table toggles and named focusable scroll regions.
- The writeup's heatmap/warning chart and replay-measure switching passed the actual browser test.
- Actual SVG bar geometry was measured for the two largest rendered bars at least5px tall in histogram, daily repayment and warning graphs. Across12 cases, Lie Factor ranged from **0.9999743 to1.0000290**, within0.95–1.05. These checks cover the measured bars, not every possible future dataset.
- The ordinary UI scorer returned **0 in every term** in all four contexts, with every chart drawn and screenshot captured. Its axe/HTML contrast checks are supplemented here by graph-specific SVG-size/clipping and explicit graph-palette checks; this is not a full WCAG certification.
- Firefox was used because host Chromium screenshot capture is unreliable. Scoring used the production CDN; chart interaction/data tests used a locally downloaded exact Plotly2.35.2 library. No Safari, Windows, native mobile, or arbitrary future dataset coverage is claimed.

## Color and vision checks

`chart-audit.py` applies the same Machado, Oliveira & Fernandes (2009), full-severity matrices used by the design skill, in linear RGB. The normal/protanopia/deuteranopia/tritanopia checks pass the declared roles: neutral text≥4.5:1, blue and gray meaningful marks≥3:1 on white. Heatmap text is dark/secondary on opaque white backing, independent of cell fill.

Twelve actual proof images were generated: crash heatmap, curve, warning graph and writeup exposure matrix, each under three simulations. The independent critic inspected the normal and simulated exposure heatmap and confirmed the numeral repair. This is a simulation, not a study of an individual's color perception. The color ramp is redundant to printed values; no claim that every adjacent ramp shade is distinguishable is made.

The static Rahil social-card palette/feed checker is not treated as a general Plotly/dark-application validator. Project-local roles and actual rendered graphs were checked instead. This task created graph QA artifacts, not an approved social media card or post. Human/publication approval remains a separate boundary.

## Independent review and reader check

One independent agent review identified three defects: fill-dependent heat-label contrast and outdated curve/history descriptions. One repair batch addressed them. Final review confirmed all three asks landed and rated each of eight criteria **4/5**, with no remaining material visual issue in the inspected artifacts. The agent did not independently rerun the reported behavior/palette tests and is not a first-time human.

Two actual final charts were shown inline and the user was asked to identify the shortest warning, its duration and whether $0 means a missing run. The user subsequently answered **“No clue.”** The check did not establish comprehension; the reason (chart interpretation, terminology, or display/access) is unconfirmed. The earlier agent review is not promoted to a human pass. A follow-up clarity correction puts the warning result and largest replay result directly in the headings and spells out $0 versus Not run. The inline host `html_preview` timed out; `html_render` reported successful display, while Firefox had already verified the exact source PNGs.

## Exact artifacts

Saved locally, ignored by Git, in [`.artifacts/spine-graphs-2026-10-26/`](../.artifacts/spine-graphs-2026-10-26/):

- [Chart render/data metrics and measured Lie Factors](../.artifacts/spine-graphs-2026-10-26/charts/chart-metrics.json)
- [UI metrics with screenshot and source hashes](../.artifacts/spine-graphs-2026-10-26/score-final/metrics.json)
- [Palette/CVD report and simulation hashes](../.artifacts/spine-graphs-2026-10-26/cvd/palette-cvd.json)
- [Named agent review](../.artifacts/spine-graphs-2026-10-26/agent-review.json)
- [Human reader-check status](../.artifacts/spine-graphs-2026-10-26/human-reader-check.json)
- [Phone crash matrix](../.artifacts/spine-graphs-2026-10-26/charts/390-light-chart-heat.png)
- [Phone warning graph](../.artifacts/spine-graphs-2026-10-26/charts/390-light-chart-warn.png)
- [Phone curve](../.artifacts/spine-graphs-2026-10-26/charts/390-light-chart-curve.png)

All seven phone/desktop light/dark figure captures, writeup capture, source hashes and CVD proofs are beside these files. They identify the actual reviewed revision; none imply live deployment or approval to publish.
