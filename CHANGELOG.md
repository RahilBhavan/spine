# Changelog

## Unreleased (refresh reliability)

- `fetch_positions` pages by borrow shares instead of health factor. Health factor moves with the oracle, so a price move during the minute-long cbBTC walk let positions slip behind the cursor; 7 of the scheduled refreshes since 2026-10-02 failed on the count check (gaps of 1 to 560 positions). After three walks a gap of up to 2 positions (`CHURN`) is accepted as live churn.
- Stale banner at 8 h (`STALE_HOURS`), not 3 h. GitHub ran the hourly cron every 4.9 h median, 7.1 h p90 over 97 runs in October 2026, so 3 h showed the banner most of the time.
- The alert issue closes itself with a comment when no market is within 10% of capacity.
- Copy says "every few hours" instead of "hourly". Outreach drafts updated to the 2026-10-25 book, the out-of-sample calibration range and the custom domain.

## Unreleased (stress grid)

- `spine/stress_grid.py` replays the cbBTC book on all seven crash paths across four LLTVs and five liquidator-capital levels and writes `data/stress_grid.csv` (one row per cell, with the loan book date). Underwater-and-unserved at the trough and realized loss are separate columns; `binds_first` records the first limit that left a queue unserved. Summary in `WRITEUP.md` section 4b.
- `backtest.simulate` returns `first_bind`, `first_bind_step` and `capital_bind_step`. Existing outputs are unchanged (identical on all 140 grid cells).

## Unreleased (Phase I, PR #10, 2026-10-24)

- Check a loan: paste a Base address and the browser asks Morpho's public GraphQL (no key) for its positions in every market on the page. It shows liquidation price, buffer, and the worst backtest crash path applied to the position.
- Freshness banner: data age on the dashboard and writeup, and a stale banner past 3 hours (`STALE_HOURS`), rechecked every minute. Replaces the 8 h stamp and 12 h notice.
- All Base markets over $10M borrowed: `spine/fetch_markets.py` runs in the hourly refresh and folds market-level data into `summary.json` as `base_markets`. The page lists Morpho-listed markets and folds unlisted ones with Morpho's warnings. A fetch failure only drops the table.
- `summary.json` gains per-market `crash_drops` and `state.market_id`; existing markets are otherwise identical on the same inputs.
- Chart code split out of `site/app.js` into `site/charts.js`.
- CI installs from `uv.lock` (`uv sync --locked --extra dev`).

## v1.1.0 (2026-09-23)

- Refresh job publishes generated data to an orphan `data` branch, so `main` gets only human commits.
- Alert and gauge share one boundary: a market at exactly 10% distance to capacity is red and opens the alert; zero capacity reads as distance 0.0.
- `summarize` fails before writing anything when positions files are missing.
- Independence disclaimer on the dashboard, writeup and README, and a note on who funds the loans.
- Link previews, favicon and social card; staleness notice when data is over 12 hours old; charts draw on scroll; accessibility fixes; weekly link check.
