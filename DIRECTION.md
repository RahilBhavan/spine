# Spine workstation pass

## Current
The prior version fits the answers on a phone and has strong accessibility checks, but reads as a long report. Market comparison is buried, the main action is repeatedly selecting an asset, the sidebar context disappears deep in the document, and there is no fast way to inspect a specific price shock. The repeated metric boxes compete with the actual argument.

## Considered compositions
1. Research report: preserve the long column and improve type. Strong for reading, weak for comparing markets.
2. Risk workstation (selected): blue section rail, persistent market context, compact answer/evidence area, market comparison table and direct shock inspection. Best fits repeated investigation while preserving the incumbent visual world.
3. Chart canvas: make large charts dominate the first viewport. Strong for expert exploration, weak for first-time readers and phone comprehension.

This is an evolution of the established app, so the three directions share the existing blue palette, system type and real-data source. A new-brand palette/font tournament would discard useful identity. No photos are needed: the product's evidence is the visual material.

## Content and flow
Risk overview → market watchlist → inspect a price shock → check a loan → book and positions → liquidation history/capacity → stress assumptions and supplier exposure → all Base markets → writeup. Existing sections and data remain present.

## Signature
Selecting a market updates its entire investigation context, including watchlist selection and price-shock comparison, without a new page. A native range control changes the inspected shock; numerical values update immediately and an optional comparison mark changes only to reflect measured data. Reduced motion keeps the final state with no choreography.

## Acceptance criteria
1. A 390px first screen contains observed total borrowing, the selected capacity threshold and replay loss, with observations/estimates and dates identified.
2. The watchlist compares all nine markets, supports a needs-attention filter, deterministic sorting and keyboard selection, and preserves selection/filter/sort in a shareable URL.
3. Shock inspection uses only exact saved curve buckets; labels its static assumptions; preserves a text/table representation; and never labels liquidatable borrow as realized loss.
4. A selected asset stays consistent across briefing, watchlist, shock inspection, book, charts and supplier exposure. Browser back/forward and reload restore the state.
5. System/light/dark theme, copy-link feedback and active section navigation work without losing query state.
6. Missing primary data has a clear retry state. Optional failures retain usable content. Keyboard, focus, contrast, touch size, narrow/desktop layouts and reduced motion are checked.
7. Existing numerical source data and Python tests stay unchanged. Scored screenshots, source hashes and a fresh visual critic record identify the actual revision and verification limits.
