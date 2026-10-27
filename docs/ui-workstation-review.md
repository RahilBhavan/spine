# Spine workstation review — 2026-10-26

Implemented locally. Named agent visual review passed; the UI comparison returns **ACCEPT**. No deployment or first-time human study is claimed.

## What changed

The user selected **risk monitoring and market investigation** as the primary audience. The page now behaves as an investigation workspace:

- A desktop section rail and persistent market/view toolbar retain context deep in the evidence. Tablet/phone layouts keep the full workflow.
- The watchlist compares all nine markets, filters thresholds of 20% or less, sorts by borrowing or room to capacity, identifies the selected row in text and preserves keyboard focus on selection. A selected market outside the filter is explicitly identified.
- A price-shock inspector reads exact saved curve samples for 0–70% falls. It shows liquidatable debt, modeled sell capacity and the amount above capacity. The model's static assumptions and the distinction from realized loss are visible.
- Capacity is reconciled beside the inspector and the liquidation chart. The documented 30% Coinbase / 50% DEX expression is shown only when it matches the saved published total. Missing or mismatched inputs produce an honest unavailable-breakdown explanation.
- Market, filter, sort, shock, heatmap scenario and metric live in the URL. Discrete changes create history entries; reload and back/forward restore the investigation.
- System/light/dark theme persists locally. Copy-link feedback is adjacent to its action. Section navigation identifies the visible section. There is a keyboard skip link.
- Missing primary data offers retry and methodology access; optional failures retain usable evidence. Invalid loan input identifies and focuses its field. Submission has loading feedback and a timeout. Generated loan-table scroll regions have keyboard access.
- Phone replay comparison uses two scenario blocks with all three measures labeled, rather than hiding the held-low result offscreen. The wider-market empty state no longer promises an unspecified future refresh.

Existing source data, observed/modeled distinctions, snapshot dates, replay-book dates, supplier exposure, loan-check functionality, chart/table alternatives and writeup remain. No new production library, frontend build step, account, backend or data provider was added.

## Design authority and skills

[PRODUCT.md](../PRODUCT.md) records confirmed product facts and the selected audience. [DESIGN.md](../DESIGN.md) versions the established Spine blue/system-sans identity as `workstation-1`; [DIRECTION.md](../DIRECTION.md) records the compositions considered and falsifiable acceptance criteria. This is an evolution of the existing analytical product, not the personal website's charcoal/yellow identity.

Applied Impeccable's Operate/craft guidance and bounded verification; Web Designer Pro's app, redesign and independent-critic workflow; the shared design-system workflow; UI/UX Pro Max's table/responsive guidance; Present Data for form/context, Tufte for integrity and direct labels, dataviz for contrast/keyboard/text alternatives, Rahil Design for exact-artifact review/provenance, and boundary discipline for URL parsing and pure comparison functions. Code-review skill was considered but no additional PR workflow or issue-tracker setup was introduced for this local design task.

The Impeccable launcher initially lacked executable permission; invoking the documented `sh` launcher worked. Product context was captured from actual repository evidence and the user's confirmed audience. No practitioner interviews or adoption claims were invented.

## Bounded review and repairs

One batched first pass found functional behavior working at five widths in both themes, but exposed accessible-label/landmark problems, narrow contrast failures on selected rows, 11px desktop subtitles and a 23px glossary target. The independent critic also identified the phone replay table, truncated theme selection, unclear capacity reconciliation and speculative wider-market availability copy.

One repair batch addressed these. The final critic inspected exact first-screen/full-page artifacts, including phone crops, and confirmed all four visual requests landed. It found no remaining material visual concern and rated each category **4/5**: task clarity, hierarchy, numerical explanation, visual craft, responsive layout, interactions, identity and evidence integrity. Interactions incorporate the supplied browser-test evidence; the critic did not independently execute the tests. Neither the critic nor the numeric score is a first-time human comprehension study.

## Verification

- Python: **28 passed**; generated data and modeling code unchanged.
- Briefing/acceptance checks: **20 assertions passed**.
- Workspace logic: filter/sort ordering, null crossings, URL boundaries, missing samples, capacity-breakdown fallback and **45 exact samples** across nine markets × five shocks passed.
- Actual Firefox browser: **320, 390, 768, 1440 and 1920px × light/dark**, all passed. Checks exercise market selection, filtering, sorting, shock presets, back/reload, native-keyboard selection, theme persistence, copy feedback, invalid loan input, first-screen answers at 390px, phone daily-table fit, no page overflow, all charts drawing and screenshots.
- Missing summary, history, replay and chart-library states passed. A failed library load retains the data-table alternative.
- Final scorer: **0.0**, every term zero across phone/desktop × light/dark. No measured axe violation, contrast failure, clipping, overflow, small target, tiny HTML text, long line, below-fold answer, layout shift, empty chart or console/page error. This is the scope of the script, not complete WCAG certification or a quality multiplier.
- Production-CDN scoring rendered every chart. Interaction tests used an exact local copy of Plotly 2.35.2 to isolate network variance.
- Present Data's figure-brief checker: PASS, with documented warnings for a stable dynamic table title, no numeric minimum contrast emitted by the scorer, and no timed human reader test. The table uses literal numbers; no new length/area encoding, axis or Lie Factor is involved.
- Impeccable detector ran once. Its tile-padding warnings refer to inherited selectors whose dashboard override removes the border/background; actual detail tiles were visually checked. Its initial mobile type-step warning was addressed with a 24/20/16px heading ladder. The detector was not rerun as an open-ended polishing loop.

Chromium capture remains unreliable on this host. Firefox was used; Windows, Safari/WebKit, native Android/iOS, color-vision simulations and a full localized-content matrix were not verified. New values have text labels and remain understandable without semantic colors. Existing Plotly SVG labels are outside the HTML tiny-text scan; table alternatives remain available.

## Exact artifacts and acceptance

[Artifact folder](../.artifacts/spine-workstation-2026-10-26/) (local, ignored by Git):

- [Metrics, screenshot hashes and site-source hashes](../.artifacts/spine-workstation-2026-10-26/metrics.json)
- [Desktop light](../.artifacts/spine-workstation-2026-10-26/desktop-light-fold.png) / [desktop dark](../.artifacts/spine-workstation-2026-10-26/desktop-dark-fold.png)
- [Phone light](../.artifacts/spine-workstation-2026-10-26/phone-light-fold.png) / [phone dark](../.artifacts/spine-workstation-2026-10-26/phone-dark-fold.png)
- Full-page PNGs and additional five-width behavior captures alongside these.
- [Named visual-review record](../.artifacts/spine-workstation-2026-10-26/visual-review.json)
- [Agent reader responses](../.artifacts/spine-workstation-2026-10-26/review.json), explicitly labeled as an agent who saw two rounds.
- [Quantitative brief](../.artifacts/spine-workstation-2026-10-26/figure-brief.json)
- [Manifest](../.artifacts/spine-workstation-2026-10-26/manifest.json)

The loop compared the prior valid 1.0 run with this 0.0 run, preserved headline evidence, verified rendered evidence and the matching named-agent reader record, and returned **ACCEPT** with no failures or pending entries. This acceptance approves this exact checked local candidate under the loop; it is not publication authority or a claim of human usability validation. No post/social image was created, so post-to-image agreement is not applicable.
