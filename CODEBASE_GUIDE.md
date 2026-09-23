# Spine: a complete codebase guide

This guide is the fastest route from “I can run it” to “I can defend its design and safely change it.” It explains the repository as a system, then gives a reading plan with concrete exercises. For financial conclusions, read `WRITEUP.md`; for the original specification and recorded decisions, read `PLAN.md`; for later corrections and unfinished work, read `ROADMAP.md`.

## 1. The one-sentence mental model

Spine takes a live lending book, observed liquidation behavior, market liquidity, and historical crash paths; it simulates whether liquidations clear before collateral becomes insufficient; then it publishes both the evidence and the policy recommendation as static artifacts.

The repository is not a trading system. It does not submit transactions, manage funds, or predict prices. It is a reproducible research pipeline.

## 2. The system in two lanes

### Lane A: the live book

```text
fetch_positions ─┐
fetch_liquidations ─> tag_coinbase ─┐
fetch_depth ─────────────────────────┼─> summarize ─> summary.json ─> site/app.js
                                    └─> history ─> history.csv
```

This lane answers: what is borrowed now, where positions sit relative to liquidation, who appears to be a Coinbase customer, what liquidity is visible now, and how much debt becomes liquidatable after each price drop?

### Lane B: model evidence

```text
fetch_prices ─────────────────────────────────────────────┐
fetch_oracle + fetch_liquidations ─> calibrate ───────────┤
Morpho transaction history ─> rebuild_book ───────────────┼─> backtest
fetch_depth ──────────────────────────────────────────────┘
                                                                 │
                            caps / writeup_tables / render_writeup <┘
```

This lane answers: how did the real system behave during lived stress, and what would today's or a reconstructed book do on seven crash paths under alternative LLTV, origination-cap, liquidity, borrower-response, and backstop assumptions?

The lanes meet through files, not function calls or a database. That makes each stage inspectable, cacheable, rerunnable, and publishable on GitHub Pages.

## 3. The domain model before the code

For a position with collateral units `c`, debt `d`, and oracle price `p`:

```text
LTV = d / (c * p)
```

A position becomes liquidatable when LTV exceeds the market's LLTV. Morpho rewards a liquidator with a liquidation incentive factor:

```text
LIF = min(1.15, 1 / (0.3 * LLTV + 0.7))
```

The position is economically underwater when there is not enough collateral, including the liquidator bonus, to repay the debt. That boundary is `LTV > 1 / LIF`.

The central research question is therefore not merely “how much debt crosses LLTV after a drop?” It is “how quickly can that debt be processed through finite liquidation capacity while market price and oracle price continue moving?” That is why this codebase contains a queue simulation rather than only a static shock table.

Three capacity scenarios make an unresolved institutional question explicit:

- A: atomic on-chain liquidation using Base DEX capacity.
- AB: A plus liquidators that hedge/sell on centralized exchanges, with a rolling capital cap.
- ABC: effectively unlimited Coinbase backstop capacity. This is hypothetical, not observed.

## 4. Walkthrough by module

### `spine/api.py`: the dependency root

Nearly every module imports this file. It owns:

- authoritative market IDs, LLTVs, decimals, Coinbase products, and oracle feed names;
- the repository-relative `data/` location;
- JSON load/save and timestamp helpers;
- time-budget parsing;
- row accessors for the compact oracle tuple format;
- HTTP retry/backoff and thin Morpho, Base RPC, and Coinbase clients.

Why centralize it: market metadata and retry behavior had diverged across scripts during the prototype. The Phase B roadmap explicitly consolidated them so changing a market or endpoint has one source of truth. The file intentionally uses the standard library to keep scheduled jobs cheap and dependency-light.

Important edge: `_http` retries broad transient failures. The `ponytail:` comment marks this as a deliberate simplification with a named upgrade path.

### `fetch_positions.py`: a consistent snapshot over a live API

Morpho caps a query at 1,000 rows and `skip` at 10,000, while cbBTC has tens of thousands of positions. `walk()` first captures null-health-factor dust positions ordered by borrow shares, then cursor-walks the rest by `healthFactor_gte`. Addresses deduplicate overlap at cursor boundaries.

Because the book can change mid-walk, `fetch()` compares the assembled unique count with a fresh unbanded count and retries up to three times. It refuses to write an inconsistent snapshot. This is the right tradeoff for analysis: stale output is preferable to internally inconsistent output masquerading as a snapshot.

Raw collateral and borrow assets are strings because on-chain integers can exceed JavaScript's exact integer range. USD projections remain numbers.

### `fetch_liquidations.py`: incremental, overlap-safe history

The GraphQL endpoint returns newest-first without an ordering option. The script pages backward with `timestamp_lte`, overlaps the previous saved day, and deduplicates by `(transaction, borrower)`. The overlap protects against same-timestamp boundaries and recently indexed events. A count mismatch aborts the write.

The file is kept as an append-like cache because rebuilding all history every hour would waste API calls. Its self-check permits tiny raw-unit bad-debt dust while rejecting meaningful bad debt.

### `tag_coinbase.py`: attribute wallets without a proprietary list

A borrower is classified by its ERC-1967 implementation address. `encode_aggregate3` and `decode_aggregate3` hand-build and parse a Multicall3 request so roughly 1,000 wallets can be checked per RPC call. If a batch fails, the code falls back to `eth_getStorageAt` one wallet at a time.

Why this method: the Coinbase and non-Coinbase populations share public Morpho markets; there is no separate market flag. The implementation slot is reproducible public-chain evidence and avoids a Dune dependency. The cost is that classification recognizes only the explicitly listed Smart Wallet implementations, so new versions require updating `IMPLS`.

### `fetch_prices.py`: deterministic stress paths

`WINDOWS` defines seven named crash periods. Coinbase's API limits each candle response, so `candles()` requests at most 300 intervals, normalizes rows into `[ts, open, high, low, close]`, and deduplicates by timestamp. Missing pre-listing altcoin data is recorded in an index rather than repeatedly fetched.

The backtest uses observed five-minute paths instead of fitted stochastic paths. This improves interpretability—each result can be tied to a known event—but does not imply that the seven paths exhaust future risk.

### `fetch_depth.py`: turn books and quotes into capacity

CEX capacity is cumulative bid-side notional inside fixed percentages of mid. DEX capacity is measured by calling Uniswap and Aerodrome quoters over increasing trade sizes and finding the largest quoted size below each slippage threshold.

The DEX comparison uses each pool's smallest-size quote as its own reference price, avoiding accidental measurement of CEX/DEX basis as slippage. `saturated=true` means the largest probed size still fit, so the reported capacity is a lower bound.

Why hand-encoded calls: the repository deliberately avoids Web3 and ABI dependencies. Selectors are documented as externally verified constants. This keeps the fetcher standard-library-only at the cost of lower-level encoding code.

### `fetch_oracle.py`: the price the protocol actually saw

Coinbase candles describe the tradable market; Chainlink logs describe the price Morpho used. This module discovers each proxy's phase aggregators, locates time boundaries by binary-searching Base blocks, and fetches `AnswerUpdated` logs in the RPC's 2,000-block windows.

Long log scans checkpoint under `data/cache/` and obey `--max-seconds`. The start is padded by a day so calibration can find crossings immediately before a named window.

### `rebuild_book.py`: historical state by event replay

Morpho's historical position snapshots were judged unreliable, so this script walks Borrow, Repay, SupplyCollateral, WithdrawCollateral, and Liquidation transactions and applies their deltas per borrower. It combines the reconstructed balances with a historical market snapshot and contemporaneous price to emit the same position schema as the live fetcher.

That schema compatibility is important: the backtest can consume “today” and dated books through the same `book_arrays()` adapter.

### `calibrate.py`: convert lived events into model inputs

Calibration joins liquidations to Chainlink prices and borrower transaction histories. It computes observed repaid/seized volume, effective bonus, daily/5-minute/hourly peaks, liquidator concentration, full-close share, and the time from crossing LLTV to liquidation.

It also fits the borrower-response abstraction used by the backtest: a deterministic share of wallets reacts after accumulating time in a warning band and repays toward a safer LTV. This exists because a frozen-book replay greatly over-predicted lived liquidations; real borrowers topped up or repaid.

The fit is intentionally simple and sensitivity-tested. It is not a behavioral truth. `WRITEUP.md` explains that two parameters fit to three major events warrant modest confidence.

### `backtest.py`: the core model

`book_arrays()` converts the JSON book into NumPy arrays and assigns every wallet a deterministic response hash. A seed changes which wallets are responsive without introducing nondeterministic output.

`reshape()` asks a counterfactual: under a different product cap and LLTV, suppose borrowers draw the same fraction of their allowed credit. It scales position LTV by `new_cap / 0.75` and clips below LLTV. This preserves the population rather than deleting currently impossible positions.

`capacity()` interpolates measured DEX/CEX depth at `LIF - 1 - margin`, then applies stress multipliers. The margin reserves room for gas and oracle risk. Scenario ABC bypasses measured capacity.

`simulate()` is the heart of the repository. At each five-minute step it:

1. rolls the trailing 24-hour CEX-capital ring buffer;
2. replenishes DEX and CEX capacity, optionally shrinking it after large hourly returns;
3. advances the lagged oracle separately from market price;
4. accumulates warning-zone time and lets designated borrowers cure;
5. queues positions over LLTV;
6. computes full or target-LTV liquidations;
7. refuses unprofitable liquidation when the market has outrun the oracle bonus;
8. serves the queue from capacity, largest debt first;
9. records realized shortfall, remaining underwater debt, queue times, volume, and trough exposure.

Performance choices matter. Positions are sorted by initial liquidation price, allowing a `searchsorted` prefix rather than scanning the whole book in calm bars. Debt-priority service uses a static ordering and vectorized 1,024-position chunks. These are documented approximations: partial repayment does not re-rank a wallet.

Why both end loss and trough exposure: historical prices often bounce before a queue clears. End-of-path loss says what the chosen replay realized; trough exposure says what was underwater and unserved at the worst print. The latter would become loss if the bounce did not occur.

The bottom half of the module is experiment orchestration. Runs have parameter keys, existing keys are skipped, and results append within a time budget. `grid`, `sens`, and `calib` serve different purposes: headline comparison, assumption sensitivity, and lived-event validation.

### `summarize.py`: the presentation boundary

The browser should not load tens of thousands of raw positions. This module reduces them to:

- per-market totals and product state;
- 2-percentage-point LTV histogram bins;
- a 0-70% price-drop liquidation/bad-debt curve;
- a health-factor CDF;
- daily liquidation history and top liquidators;
- top borrowers and Coinbase flags;
- measured depth and distance-to-capacity.

This is an anti-corruption layer between research data and UI needs. Tests in `tests/test_data.py` protect the compact schema and core monotonicity.

### Small derivation and publication modules

- `history.py` appends summary rows only when the last sample is roughly an hour old.
- `caps.py` computes rolling seven-day drawdown percentiles, volatility, recommended origination caps, and the SmartLTV comparison.
- `writeup_tables.py` treats generated JSON as the source of every numeric table. `find()` requires exactly one matching run, turning missing or duplicate experiment cells into loud failures.
- `render_writeup.py` implements only the Markdown subset this document uses and inserts Plotly figures. A full Markdown dependency would be easier but contrary to the no-dependency design.

### `site/`: a static state machine

`index.html` provides semantic containers and controls. `style.css` defines the visual system, responsive layout, dark mode, and risk colors. `app.js` owns UI state in a few module-level variables and rerenders with Plotly.

The live tab loads `summary.json`. The backtest tab lazily loads the much larger `backtest.json`, builds a predicate for default/fitted grid rows, and renders heatmaps for LLTV × crash path, liquidator capital, and warning time. Lazy loading keeps the default dashboard fast.

The site is served from the repository root because paths are `../data/...`. Opening `site/index.html` directly with `file://` will fail browser fetch restrictions.

One technical debt item is explicit in current code: Python's JSON writer emits `Infinity` for unlimited-capital rows, so JavaScript replaces it with `1e999` before parsing. This works but is not strict JSON.

### Workflows

CI installs Python 3.12, NumPy, and pytest and runs the suite. The hourly refresh runs the live pipeline, advances the resumable backtest, force-pushes the generated artifacts to the `data` branch as one orphan commit, stages a minimal `_site`, and deploys GitHub Pages. Each run starts by restoring `data/` from that branch, so appending files (history.csv, liquidations, the wallet cache, backtest.json) carry over. `main` keeps one frozen snapshot and gets only human commits.

This architecture makes the repository itself the data store with zero infrastructure. The `data` branch keeps only the latest state, so the repository does not grow per run; the cost is no per-run audit trail in git, and publication health stays coupled to refresh/model health.

## 5. Why the project looks this way

The following are documented decisions, not guesses:

- Static site over a server: source APIs are public/CORS-accessible, and static publication lowers operational burden.
- Real crash paths over purely synthetic paths: results are legible and auditable against named events.
- Live depth times stress multipliers: historical order books are paid; uncertainty is exposed through sensitivities.
- Reconstructed lived-event books: current positions would be the wrong population for calibration.
- Today's reshaped book for pre-launch crashes: no historical product book exists, so the counterfactual is stated directly.
- All markets in the dashboard, deep modeling for cbBTC/WETH: they dominate book size and have the strongest liquidity evidence.
- Plain scripts and files over services/classes: the pipeline is small, sequential, inspectable, and cron-driven.
- Generated tables over hand-entered prose numbers: it prevents the recommendation from silently drifting away from model output.
- Assertions in executable scripts plus pytest references: scripts validate live invariants; tests protect deterministic algorithms and file contracts.

The following rationales are reasonable inferences from code and history, not explicitly recorded decisions:

- Largest-debt-first likely approximates bots preferring economically valuable liquidations while keeping service deterministic.
- The static debt ranking inside a run prioritizes speed and reproducibility over perfect re-ranking after partial fills.
- Module-level UI state favors a small dependency-free page; it would become hard to maintain if interactive complexity grows substantially.

## 6. How to read the repository without getting lost

Use four passes. Do not start with all 509 lines of `backtest.py`.

### Pass 1 — product and contracts (about 90 minutes)

Read, in order:

1. `README.md`
2. `PLAN.md` sections 1, 4, 6b, and 7
3. `WRITEUP.md` through section 4
4. `CONTRIBUTING.md`
5. `spine/api.py`

Exit criterion: explain LLTV, LIF, the bad-debt boundary, scenarios A/AB/ABC, and why the project has both a dashboard and a replay model.

### Pass 2 — one live datum end to end (2-3 hours)

Read `fetch_positions.py`, `tag_coinbase.py`, `fetch_depth.py`, `summarize.py`, then the first 230 lines of `site/app.js`.

Exercise: pick cbBTC total borrow. Trace its source field from Morpho response, through `positions_cbBTC.json`, `summarize_market()`, `summary.json`, and `renderCards()`. Repeat for distance-to-capacity.

Exit criterion: name the producer and consumer of every field in one market's `summary.json` object.

### Pass 3 — one historical event end to end (half a day)

Read `fetch_prices.py`, `fetch_oracle.py`, `fetch_liquidations.py`, `calibrate.py`, and `rebuild_book.py`.

Exercise: choose Feb 2026. Draw the join keys and time axes used to connect candle lows, oracle blocks, borrower histories, and liquidations. Identify where exchange time, oracle time, and block time can disagree.

Exit criterion: explain why calibration needs both candles and Chainlink logs, and why a reconstructed book is preferable to today's book.

### Pass 4 — own the model (one day)

First read `tests/test_backtest.py`; its brute-force `reference()` is a clearer executable specification than the optimized model. Then read `backtest.py` in this order: constants/defaults, `book_arrays`, `reshape`, `capacity`, `simulate`, `run`, orchestration.

Exercises:

1. Work one single-position liquidation on paper and verify `test_partial_liquidation_repays_to_target`.
2. Explain why the Tier B test clears at bars 1, 289, 577, and 865.
3. Change only an in-memory synthetic test parameter—response share, oracle lag, or capacity—and predict the direction of every output before running it.
4. Trace one row from `backtest.json` into `writeup_tables.find()` and the site's heatmap selection.

Exit criterion: explain every `DEFAULTS` parameter, identify which are measured, fitted, assumed, or sensitivity-only, and describe at least three model ceilings.

## 7. A practical change checklist

Before editing:

1. Identify the artifact contract you are changing.
2. Find both its producer and every consumer with `rg`.
3. Decide whether the change affects live facts, calibration, model behavior, presentation, or more than one lane.
4. Read the relevant acceptance criteria in `ROADMAP.md`.

While editing:

1. Keep network and argv work under `__main__`.
2. Preserve resumability and deduplication.
3. Put shared behavior in `api.py`, but do not create abstraction merely to reduce a few obvious lines.
4. Label deliberate approximations with a concise `ponytail:` comment and an upgrade path.
5. Change producers instead of generated files.

After editing:

1. Run the narrow module self-check.
2. Run the relevant targeted test, then the full suite.
3. Regenerate downstream artifacts if their producer changed.
4. Compare model outputs when behavior should remain constant.
5. Report networked or visual checks you could not run.

## 8. Known ceilings and unresolved questions

- Historical depth is approximated from current depth, not observed for most events.
- Liquidator capital is inferred from a non-binding observed day and is the largest result lever.
- Borrower response is a low-dimensional fit on few events.
- The oracle model for counterfactual events is a simple lag over candle lows.
- A static liquidation service rank does not re-rank after partial repayments.
- Coinbase affiliation detects known Smart Wallet implementations, not organizational ownership of every address.
- The browser's `Infinity` repair is a compatibility workaround rather than a clean data contract.
- The dashboard covers alt markets more confidently than the backtest does; missing DEX venues and shorter price histories weaken alt conclusions.
- Unknown: which planned Phase G changes in the uncommitted `ROADMAP.md` the owner intends to implement and in what review units.

## 9. What “understand everything” means here

You are ready to work independently when you can:

- derive liquidation and bad-debt thresholds from LLTV;
- trace every published number to a generated file and producer;
- explain the live and historical lanes without looking at this guide;
- distinguish measured, reconstructed, fitted, assumed, and hypothetical inputs;
- predict the qualitative effect of each backtest parameter;
- state why each fetcher can safely resume or refuses to write;
- identify the test or acceptance check for a proposed change;
- describe which conclusions remain valid when a major assumption changes.

That is a more useful standard than memorizing every function. The code is small enough to read, but the real skill is knowing which evidence supports each conclusion and where uncertainty enters the pipeline.
