# Architecture reference

## System shape

```text
Morpho GraphQL ──> positions / liquidations ─┐
Base RPC ────────> wallet tags / oracle logs ├─> summarize ─> summary.json ─> dashboard
Coinbase/Kraken ─> candles / CEX depth ──────┤
DEX quoters ─────> DEX capacity ─────────────┘

historical events + oracle logs ─> calibrate ─> calibration.json ─┐
historical transactions ─────────> rebuild_book ─> dated books ──┼─> backtest.json
crash candles + depth + books ────────────────────────────────────┘

backtest + calibration + summary + caps ─> tables/writeup renderer ─> WRITEUP.md / site/writeup.html
```

## Components and entry points

- `spine/api.py`: shared market registry, paths, JSON I/O, time-budget helper, HTTP retry/backoff, and public API clients. Every other Python module depends on it.
- `spine/fetch_positions.py`: complete current debt-position snapshots. It works around GraphQL's 10,000-row skip ceiling with a health-factor cursor and refuses to write inconsistent live walks.
- `spine/fetch_liquidations.py`: incremental liquidation history. It overlaps the prior day, deduplicates by transaction and borrower, checks the total, then writes.
- `spine/tag_coinbase.py`: identifies Coinbase Smart Wallet proxy implementations via Multicall3 with a per-address storage fallback.
- `spine/fetch_prices.py`: cached five-minute crash-window candles and daily histories from Coinbase Exchange.
- `spine/fetch_depth.py`: current CEX bid depth and executable DEX quote capacity at model-relevant slippage levels.
- `spine/fetch_oracle.py`: Chainlink `AnswerUpdated` paths from Base logs, with block-range checkpoints.
- `spine/rebuild_book.py`: replays Morpho transactions to reconstruct dated books for events the product actually lived through.
- `spine/calibrate.py`: measures liquidation volume, bonus, latency, concentration, and fits borrower-response/liquidation-style parameters.
- `spine/backtest.py`: NumPy liquidation-queue simulation, grids, sensitivities, lived-event calibration, resumable result store.
- `spine/summarize.py`: converts large raw snapshots into the compact, browser-safe `summary.json` contract.
- `spine/history.py`: appends approximately hourly summary metrics to `history.csv`.
- `spine/caps.py`: derives origination caps from historical seven-day drawdowns and prints the SmartLTV cross-check.
- `spine/writeup_tables.py`: prints every numeric Markdown table from generated artifacts.
- `spine/render_writeup.py`: intentionally small Markdown-to-HTML renderer plus generated Plotly figures.
- `site/app.js`: stateful rendering layer for live and backtest views; it reads only generated JSON.
- `.github/workflows/ci.yml`: Python 3.12 unit/data-contract checks.
- `.github/workflows/refresh.yml`: hourly fetch, derive, commit, stage, and GitHub Pages deployment pipeline.

## Core data contracts

- `positions_<market>.json`: raw integer collateral/debt strings plus USD views and market state.
- `liquidations_<market>.json`: append-only liquidation events with raw repaid/seized/bad-debt values.
- `coinbase_wallets.json`: lowercase address to Smart Wallet version or null.
- `prices/*.json`: sorted `[timestamp, open, high, low, close]` rows.
- `oracle/*.json`: sorted `[timestamp, block, price]` rows; use accessors in `api.py`.
- `depth.json`: CEX books summarized by slippage and DEX quote grids/capacities.
- `calibration.json`: observed lived-event metrics and fitted inputs.
- `backtest.json`: defaults, calibrated parameters, and keyed simulation runs.
- `summary.json`: compact browser contract: totals and per-market state, histograms, curves, tables, and depth.

## Trust and change boundaries

External APIs and live books can change during a run. Fetchers therefore pace requests, retry transient failures, deduplicate overlaps, validate counts, and write only after invariants pass. The browser never consumes raw position files. Model assumptions are explicit parameters and sensitivity rows rather than hidden constants where practical.

