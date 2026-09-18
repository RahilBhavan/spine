# Roadmap: from prototype to a maintained project

Status 2026-09-18: Phases A-E done (E1 item 3, alt-asset replays, deferred; item 6 lands as
`calibrate --since` plus `data/windows.json`). The partial-liquidation model changed the
headline: under calm-day liquidator behaviour (trim to 74%), LLTV barely moves March 2020
losses; liquidator policy and capital do. See WRITEUP.md section 4. Phase F remains.

Written 2026-09-17 after the two-axis review (see PLAN.md §6b for what the build changed). Each
phase is one or two `runner` dispatches with a `reviewer` pass, in the order below. Nothing here
adds a framework, a server, or a paid data source.

## Phase A: fixes that change results (1 day)

The review found three modelling gaps that bias bad debt downward and one contract the docs claim
but the code lacks.

1. **Capacity margin.** `backtest.capacity()` reads depth at exactly LIF-1 (4.38%). Add `margin`
   (default 0.01): depth is read at LIF-1-margin, since a liquidator needs gas and oracle slack.
   Depth tables already carry 3% and 4.38% points; interpolate between measured slippage points
   rather than adding a new fetch.
2. **Tier B capital cap.** Scenario AB adds CEX depth with no limit on how much inventory
   CEX-hedged liquidators can carry. Cap Tier B at `cex_cap_usd` per rolling 24h, default the
   observed max single-day repaid on the market (Feb 5 2026, $96.8M, read from
   `data/calibration.json`), overridable.
3. **Assert the calibration.** `backtest.py calib` prints simulated/realized ratios; make the
   `__main__` assert them: every cbBTC lived event within 25% under AB at (s*, d*). If refitting
   after 1 and 2 moves (s*, d*), that is the point.
4. **`--max-seconds` for backtest.** Grid runs append to `data/backtest.json` keyed by parameters;
   make the script skip keys already present and stop cleanly on the budget, like the fetchers.

Acceptance: `calib` passes its new assert; grid regenerated at the new (s*, d*); the
WRITEUP.md tables re-cut from `backtest.json` (a script, `spine/writeup_tables.py`, prints the
Markdown tables so the numbers cannot drift from the data again).

## Phase B: consolidation (1 day)

Standards findings. No behaviour change; the self-checks and calibration output must be identical
before and after.

1. One shared helper set in `spine/api.py`: `DATA` path, `load(name)`, `save(name, obj)`,
   `day_ts(date)`, `budget(max_seconds)` (a function returning a "still within budget" closure),
   and a `feed` field on `MARKETS` ('BTC', 'ETH', ...) replacing the three diverging local maps.
2. No classes: `calibrate.Oracle` becomes two functions over the sorted rows; `Budget` becomes the
   shared helper. Oracle rows get a tiny accessor set (`row_ts`, `row_block`, `row_price`) so
   magic column indices disappear.
3. argv parsed only under `__main__` in every script (importing `WINDOWS` must not touch argv).
4. Kraken goes through `api.get_json(url)`; `coinbase_get` becomes a thin wrapper over it.
5. `CONTRIBUTING.md` (half a page): the rules the reviewer had to infer from `api.py`, so the next
   review has a document to cite. Stdlib only outside `backtest.py`; no classes; argv by hand;
   `__main__` self-check with asserts; long scripts take `--max-seconds` and resume; `ponytail:`
   comments mark deliberate ceilings.

## Phase C: tests and CI (half a day)

One `tests/test_backtest.py` with the brute-force per-position reference the reviewer wrote in
scratch: on a 1,500-position sample and a short synthetic path, `simulate()` must match the
reference exactly under ABC and within 1% under A/AB, at resp_share 0 and 0.7. One
`tests/test_data.py` that validates the JSON shapes the site reads (`summary.json`,
`backtest.json`, `calibration.json`) so a fetcher change cannot break the page silently.
`.github/workflows/ci.yml` runs both on pull requests, with the venv from `pyproject.toml`.
The hourly `refresh.yml` stays separate and gets `python -m spine.backtest --max-seconds 600`
appended so the grid tracks the live book.

## Phase D: dashboard v2 (1 day)

1. **Backtest tab** reading `backtest.json`: bad-debt heatmap (LLTV × window) per market and
   scenario, a scenario toggle, and the sensitivity strip for k_cex.
2. **Distance-to-capacity gauge**: the price drop at which liquidatable borrow exceeds modeled
   capacity (AB) for each market, from `summary.json`. This is the one number a risk desk would
   check each morning.
3. Health-factor CDF next to the LTV histogram; alt markets get their CEX depth line.
4. Writeup page rendered at build time: `spine/render_writeup.py` turns `WRITEUP.md` into
   `site/writeup.html` with a 40-line stdlib Markdown subset (headings, paragraphs, tables, bold,
   links, lists) so the `marked` CDN goes away. Figures: two Plotly charts embedded from the same
   JSON (bad-debt heatmap, warning-time bars).
5. Snapshot history: the hourly job appends one row per market (borrow, collateral, book LTV,
   liquidatable at -10/-20/-30, capacity) to `data/history.csv`; the dashboard gets a time series
   of book LTV and the distance-to-capacity gauge. This is what makes "live" mean something over
   months.

## Phase E: model v2 (2 days)

1. **Partial liquidations.** Real liquidations are 28-51% full; the model seizes in full. Let
   liquidators seize the minimum of full and what clears at the bonus, and re-queue the rest.
   Refit (s*, d*); the responsive share should fall because partial fills explain part of the gap.
2. **Depth collapse as a function of the path**, not a constant: k_cex(t) = f(realized 1h
   volatility), fit to the two Kaiko data points we have (Oct 10 2025, >90% top-of-book; FTX,
   about half) and stated as such. Replaces the 0.3 default with something the path drives.
3. **Alt-asset replays** with CEX-only depth, Coinbase redemption as the only disposal route, and
   the alts' own paths (XRP, SOL, DOGE from `data/prices/`). Gives the per-asset book cap a
   number instead of a rule of thumb.
4. **Origination cap derivation** per PLAN.md §4: p95 week-long drawdown from `daily_*.json`,
   cap = LLTV minus the buffer that keeps the median new loan out of liquidation. Add the
   SmartLTV cross-check (RiskDAO formula, inputs from `depth.json` and daily vol).
5. **Uncertainty**: bootstrap the responsive-share assignment (10 hash seeds) and report bad-debt
   ranges, not point values, in the writeup tables.
6. **Re-calibration on new events**: `calibrate.py` gets a `--since` mode that detects any day
   with liquidations above a threshold and adds it as a window, so the fit updates itself.

## Phase F: publication (half a day plus your decisions)

1. Flip the repo public, enable Pages (Actions source), confirm the hourly deploy lands. As of
   2026-09-17 the `refresh` job succeeds and has committed eight snapshots, and the `deploy` job
   fails on `actions/deploy-pages` because Pages is not enabled on the private repo. Nothing to
   fix in the workflow; it is the account step. Cron has been firing every 5-6 hours, not hourly
   (GitHub schedules are best-effort); if hourly matters, trigger from an external ping instead.
2. Writeup v2 with Phase A/E numbers and ranges, figures from JSON, a changelog section listing
   what each phase changed in the recommendation.
3. Answer the three open questions from PLAN.md §8 (Coinbase self-liquidation, audience, hosting)
   because they set the writeup's tone and the ABC scenario's weight.
4. Optional reach: Morpho governance forum post (they run this market's Dune dashboards), a Dune
   dashboard mirroring `summary.json` for people who live there, and a short thread with the
   warning-time table, which is the most shareable single result.

## Later (from PLAN.md §9, still not now)

Liquidator leaderboard with profit, supplier-side vault exposure, Chainlink deviation replay,
alert bot on the distance-to-capacity gauge, Aave/TradFi comparison table in the writeup.

## Order and effort

A (1d) -> B (1d) -> C (0.5d) -> D (1d) -> E (2d) -> F (0.5d): about six working days, same as
the original build. A and B are independent of each other but B must land before C's tests
freeze the interfaces. D and E can run in parallel (disjoint files). F waits on E.
