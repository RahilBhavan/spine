# Roadmap: from prototype to a maintained project

Status 2026-09-19: Phase G (pipeline, model, code fixes) planned below. Status 2026-09-18: Phases A-E done (E1 item 3, alt-asset replays, deferred; item 6 lands as
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

## Phase G: keep the live parts live (review of 2026-09-19)

Written 2026-09-19 after reading the model, the workflows and the last six refresh runs. Three groups, three
`runner` dispatches with a `reviewer` pass each, in this order: G1 changes what the cron commits and what the
backtest keys on, so G2's new grid rows must land after it; G3 is a behaviour-preserving cleanup that G1/G2's
regenerated `backtest.json` verifies.

### G1. Pipeline (one PR, half a day)

Findings: the hourly `backtest --max-seconds 600` has done zero runs since the grid was first cut (every row is
keyed `book='today'`); each snapshot commits ~25 MB of JSON and `.git` is 99 MB after 15 snapshots; two of the
last six refresh runs died on level asserts (`unrealized_bad_debt_usd > 0` for Mar 2020 flipped as the book
moved) and took the Pages deploy down with them; the push has no rebase; `cex_cap_usd` in every run key is a
float read from `calibration.json` at import.

1. **Round the capital cap before it enters a key.** `cex_cap_default()` returns `round(max(days), -5)`; the
   stale check in `calibrated()` compares the same rounded values. Every existing grid row stops matching, which
   is fine because item 2 regenerates them anyway. Do this first so the grid is cut once.
2. **Grid rows carry the book date.** `today_book()` also returns the label
   `datetime.date.fromtimestamp(raw['fetched_at'], UTC).isoformat()`; `grid()` and `sensitivity()` pass
   `dict(book=label)` instead of `'today'`. `save()` adds `latest_book` to the top level: the live label with the
   most rows (ties to the newest), so the site and `writeup_tables` read a complete grid while a new date fills in
   over several cron runs. `save()` prunes live rows (no `calib_window`) whose label is neither `latest_book` nor
   the newest label. `writeup_tables.BASE['book']`, `backtest.table()` and `site/app.js:274,278` read
   `BT.latest_book` instead of the literal `'today'`. Measure one full cbBTC+WETH grid+sens locally and record
   the minutes in this file; if it exceeds four cron runs of 600 s, label by ISO week instead of day.
   Measured 2026-09-19: full cbBTC+WETH grid+sens+calib took 8 min (2008 runs, one invocation, M-series laptop); day label kept.
3. **Stop committing the positions files.** Drop `data/positions_*.json` from the `git add` line in
   `refresh.yml`, `git rm --cached` them, add the pattern to `.gitignore`. Keep `coinbase_wallets.json` and
   `liquidations_*.json`: both are append-only caches that delta-compress well and without them the cron would
   re-tag 70k wallets and re-page every liquidation each run. `tests/test_data.py` already skips on absent files.
   README gets one line: `fetch_positions` is the first thing to run on a fresh clone. Rewriting history to
   reclaim the 99 MB is a separate decision (destructive); not part of this item.
4. **Level checks behind `--check`.** `api.argv_max_seconds()` also strips and returns a `check` flag. Level
   asserts (`summarize.py:148`; the Jun 2026 zero-bad-debt and Mar 2020 exposure asserts in `backtest.py
   __main__`) run only under `--check`. Invariants stay unconditional: histogram sums to borrow, curve monotone,
   Tier B ring window is exactly 288 bars, calibration ratios within 25%. The cron omits `--check`;
   CONTRIBUTING gets the sentence "paste `--check` output in the PR".
5. **`refresh.yml` order.** Steps become: fetch + summarize + history + render_writeup; backtest in its own step
   with `continue-on-error: true`; commit (with `git pull --rebase origin main` before `git push`); stage and
   upload. A model failure then leaves a warning annotation and a stale Backtest tab, not a dead dashboard.
6. **Staleness on the page.** `app.js` computes hours since `DATA.generated_at` (and `BT.generated_at` on the
   Backtest tab); past 8 h the timestamp gets a `stale` class (red, from `:root`). Six lines of JS, two of CSS.
7. **One interpreter in the docs.** README and CONTRIBUTING use `.venv/bin/python -m spine.<x>` throughout, with
   `uv venv .venv && uv pip install numpy pytest` as the setup line. `ci.yml` is unchanged.

Acceptance: two consecutive scheduled refresh runs green; `git count-objects -vH` size-pack grows by under 2 MB
across them; `backtest.json` has `latest_book` equal to a date and zero rows with `book == 'today'`; the Backtest
tab and `writeup_tables` render from it; `python -m spine.summarize` passes without `--check` on a book where the
-30% liquidatable figure is outside $150-500M (patch the loaded JSON in a one-off shell to prove it).

### G2. Model and writeup (one PR, one day)

1. **Hold at the low.** `hold_bars` (default 0) in `DEFAULTS` and `key()`. `crash_path()` inserts `hold_bars`
   copies of the trough low immediately after the trough index, before the bounce. Sensitivity adds, for cbBTC on
   Mar 2020 and May 2021 at LLTV 0.86 / 0.80 / 0.77, `hold_bars` in (12, 288) (one hour, one day) under AB and
   ABC. `writeup_tables` gets a "held at the low" table: loss by end of path at hold 0 / 1 h / 1 day next to the
   trough exposure. Writeup section 4 gains the table and section 7's second bullet becomes a number.
2. **Ranges in the headline rows.** `writeup_tables.seven_paths()` and `lltv_grid()` print `point (min-max)` over
   `SEEDS` wherever seed rows exist (Mar 2020 and May 2021 at 0.86 / 0.80 / 0.77). Sensitivity adds
   `(resp_share, react_min)` in {0.6, 0.7} x {60, 120} on the same two windows so the plateau claim in section 3
   has four cells behind it; `borrower_response()` prints them.
3. **Alt replays.** `capacity()` treats a missing `depth['dex'][market]` as zero DEX depth (CEX only, which is
   the alts' reality). `grid()` skips windows with no price file for the market (`candles_for` returns None; SOL
   has no Mar 2020 or May 2021). Run `grid --market cbXRP` and `--market SOL` at LLTV 0.625 / 0.70 with caps 0.50
   / 0.55 (add 0.55 to the cap list; it is the product's actual max draw). `writeup_tables` gets an alt table:
   per window, AB liquidated / loss / exposure at trough / queue p95, plus the multiple of today's book at which
   Oct 2025 first produces loss (rerun with `debt *= m` for m in 1, 2, 4, 8; a `book_multiple` param in
   `reshape()`), which is the number section 6's size rule needs. `test_data.py` checks the alt rows exist.
4. **Book date stamp.** `render_writeup` reads `latest_book` from `backtest.json` and inserts "Backtest book as
   of <date>; dashboard refreshes hourly" after the italic intro. `writeup_tables` prints the same line first.

Acceptance: `backtest.py --check` passes; `writeup_tables` output pasted into WRITEUP.md with no hand-typed
numbers changed; the calib ratios at (s*, d*) are unchanged to two decimals (G2 adds runs, it does not change
the model on the default path); `pytest -q tests` green.

### G3. Code (one PR, two hours)

1. **One event helper in `simulate()`.** The repay / full-close / seize computation appears twice (the
   clear-everything branch and the chunked branch). `events(debt, coll, p, L, tau, fb)` returns
   `(rep, full_ev, seize, under)`; both branches call it.
2. **`tests/test_summarize.py`.** Five synthetic positions (two Coinbase, one over LLTV, one with zero
   collateral): `ltv_hist` sums to total borrow, `liquidatable_curve` is monotone and its drop-0 row equals the
   over-LLTV set, `distance_to_capacity` returns the first exceeding drop and None when cap is 0 or never
   exceeded, `hf_cdf` starts at 0 and ends at 1 when every position has a health factor.

Acceptance: `pytest -q tests` green; `backtest.py calib` ratios and every `data/backtest.json` row identical to
1e-9 before and after G3.1 (diff the file); `python -m spine.summarize` output byte-identical.

### Order and effort

G1 (0.5 d) -> G2 (1 d) -> G3 (0.25 d). G1.1 before G1.2 so the grid is regenerated once. G2.3 depends on G1.2's
`latest_book`. G3 last so the regenerated grid is its reference.

Follow-up 2026-09-19: alt cap number in writeup_tables (no replay), scenario A skipped for CEX-only markets, writeup_tables reads via saved_runs().
