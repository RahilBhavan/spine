# Spine: live risk dashboard over Coinbase's on-chain loan book

Plan written 2026-09-15 from live API probes and three research sweeps. Every number
below was verified today unless marked "unverified".

## 1. What this is

Coinbase's crypto-backed loans are positions in public Morpho Blue markets on Base.
Every borrower is a per-user Coinbase Smart Wallet, so the whole book (collateral,
debt, liquidations) is queryable. This project builds three things on top of it:

1. **Live dashboard**: realized LTV distribution of the book, per market, Coinbase-only
   vs everyone, refreshed from the Morpho API in the browser.
2. **Time-to-liquidate (TTL) model**: how long it takes to clear the liquidation
   queue for a given price shock, given real order-book and DEX depth, and what bad
   debt results when depth runs out.
3. **Haircut backtest + writeup**: replay March 2020, May 2021, FTX Nov 2022,
   Aug 2024, plus the three events the book has actually lived through (Oct 2025,
   Feb 2026, Jun 2026), across a grid of LLTV / origination-LTV settings, and argue
   for specific haircut levels per asset.

## 2. Ground truth (verified 2026-09-15)

### The markets (all Base, chainId 8453, loan asset USDC `0x8335…2913`, IRM AdaptiveCurve `0x4641…2687`)

| Collateral | LLTV | Market ID | Borrow today | LIF (bonus) | Bad-debt LTV = 1/LIF |
|---|---|---|---|---|---|
| cbBTC `0xcbB7…33Bf` | 86% | `0x9103c3b4e834476c9a62ea009ba2c884ee42e94e6e314a26f04d312434191836` | $1,413M | 1.0438 (4.38%) | 95.8% |
| WETH `0x4200…0006` | 86% | `0x8793cf302b8ffd655ab97bd1c695dbd967807e8367a65cb2f4edaf1380ba1bda` | $83M | 1.0438 | 95.8% |
| cbETH | 77% | `0x0ca10126f6c94cbd9cf0a48cc9516ae5e3dec5aa68303e6d988ee37c5149bf0d` | $11M | 1.0846 | 92.2% |
| cbXRP | 62.5% | `0xd4a903dc6d949519060c7707f9604fdc9772c046e05c2e3a8fce0bd7196e4109` | $48M | 1.1274 | 88.7% |
| SOL | 62.5% | `0x7dc02ff6c536b1d49d7fba770438d79f5bd1f1c78884629b7d1aaee19675782b` | $5M | 1.1274 | 88.7% |
| cbDOGE, cbADA, cbLTC, JitoSOL | 62.5% | see research notes | small | 1.1274 | 88.7% |

- Morpho Blue core: `0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb`.
- cbBTC/USDC: supply $1.571B, collateral $2.86B, utilization 90%, 70,496 positions
  (39,106 with debt), 14,009 liquidation txs since creation, realized bad debt $0.
  Book-level LTV ~49%. Largest single borrower ~$5.2M debt.
- Oracle: MorphoChainlinkOracleV2 wrapping Chainlink BTC/USD `0x64c9…848F`; USDC
  hard-pegged to 1. Oracle lag is a real parameter in the model.
- Product terms (secondary press; Coinbase help pages 403 to fetch): max draw LTV
  75%, liquidation at 86%, penalty 4.38%, caps $5M BTC / $1M ETH / $100k alts.
- Coinbase borrowers are identified by ERC-1967 implementation slot of the borrower
  address resolving to Smart Wallet impl `0x000100ab…9E72` (v1.0) or
  `0x00000110…534d` (v1.1). No dedicated market; public borrowers share it.
- Morpho liquidation: LIF = min(1.15, 1/(0.3·LLTV + 0.7)). Bad debt when collateral
  hits zero with debt left; socialized pro rata to suppliers.

### Stress events (Coinbase 5m candles, worst high-to-low inside each window)

| Event | BTC P2T | BTC worst 4h | BTC worst 24h | ETH P2T | ETH worst 4h | ETH worst 24h |
|---|---|---|---|---|---|---|
| Mar 2020 | -58% | -35% | -50% | -64% | -33% | -52% |
| May 2021 | -50% | -26% | -32% | -58% | -38% | -46% |
| FTX Nov 2022 | -28% | -15% | -19% | -36% | -22% | -28% |
| Aug 2024 | -30% | -11% | -20% | -38% | -23% | -28% |
| Oct 2025 | -15% | -10% | -13% | -26% | -15% | -20% |
| Feb 2026 | -34% | -9% | -18% | -43% | -12% | -20% |
| Jun 2026 (May 30-Jul 5) | -22% | -7% | -9% | -26% | -8% | -14% |

Windows in `spine/fetch_prices.py` are wider than the research script's (they include the pre-crash run-up), so the Jun 2026 row differs from the first draft.
Realized book history: Feb 5 2026 ~$90.7M liquidated in one day across ~2,000 users;
Jun 2-5 2026 ~$57M / 3,784 users; Jun 25 ~$9.5M. Zero bad debt through all of it.
Script: `research/crash_table.py` (stdlib, ~2 min).

### Liquidity (today)

- Coinbase BTC-USD bids within 2% of mid: ~$22M; within 5%: ~$38M (mid $76.4k).
- All cbBTC/USDC DEX TVL on Base: ~$30M across Aerodrome and Uniswap pools;
  cbBTC/WETH ~$50M.
- Morpho's own stress table: -15% BTC makes $55M liquidatable, -30% $315M, -50% $1.1B.
- Kaiko on Oct 10 2025: top-of-book depth fell >90% intraday on major venues.
- So: at -30%, ~$315M must clear through ~$30M of on-chain depth plus a CEX book that
  holds ~$40M within 5% in calm conditions. That mismatch is the central finding.

### Data access (all free, all CORS-open from browsers)

- Morpho GraphQL `https://blue-api.morpho.org/graphql`: 750 req/min, `first` max
  1000, `skip` max 10,000 (so 70k positions need slicing by `healthFactor` or
  `collateral` bands). `marketCollateralAtRisk` returns a ready-made price-drop curve.
  `marketTransactions(type_in:[Liquidation])` gives every liquidation with liquidator,
  repaid, seized, badDebt. Historical position snapshots are unreliable; rebuild from
  events.
- Base RPC `https://mainnet.base.org`: 2,000-block `eth_getLogs` windows;
  `base.drpc.org` allows 10,000. Event topics for all 8 Morpho events are in the
  research notes.
- Prices: Coinbase Exchange candles (1m back to 2015, 300/call, 10 req/s, no key);
  Bitstamp and Bitfinex as cross-checks; Binance REST is geo-blocked from US IPs but
  `data.binance.vision` monthly zips work.
- Live depth: Coinbase L2 (full book), Kraken (500 levels). Historical depth is paid
  (Tardis $350+/mo; first-of-month days are free). We do not buy it: use live depth
  times a documented stress multiplier.

## 3. What already exists, and how we differ

Morpho's Dune dashboard (dune.com/morpho/coinbase-on-chain-loan-positions-liquidations-dashboard)
already has the LTV histogram, liquidation-price buckets, Coinbase vs non-Coinbase
split, and a static "-X% => $Y liquidatable" table. We cite it and go past it:

| Existing | Ours |
|---|---|
| Static shock table (what crosses the line) | Dynamic: what actually clears, how fast, what turns into bad debt |
| BTC market only | All nine Coinbase markets, haircuts per asset |
| No liquidator analysis | Who liquidates the book, their capacity, and their realized latency in Feb/Jun 2026 |
| No historical replay | Seven crash paths at 5m resolution against the real book |
| No recommendation | Argued haircut per asset with the numbers that justify it |

No Gauntlet/Chaos/Block Analitica report on this market exists (searched, none found).
The only closed-form LLTV rule in the wild is RiskDAO's SmartLTV
(LTV = exp(-c·sigma/sqrt(l/d)) - beta); Chaos Labs uses a p99 24h VaR under GARCH
paths with agent-based liquidators. We use the Chaos structure with real paths
instead of simulated ones, and report SmartLTV as a cross-check.

## 4. The model

Per position i: collateral c_i (units), debt d_i (USDC). Price path p(t) at 5m steps.
LTV_i(t) = d_i / (c_i · p(t)).

**Liquidation queue.** At each step, positions with LTV > LLTV enter the queue with
size s_i = d_i·LIF worth of collateral to sell. Positions with LTV > 1/LIF that have not
been cleared realize bad debt = d_i - c_i·p(t)/LIF... precisely, the shortfall after
full seizure.

**Liquidator capacity per step** (USD of collateral absorbable at slippage <= LIF - 1
minus a margin m for gas and oracle risk, default m = 1%):
- Tier A, atomic on-chain: DEX depth within (LIF-1-m) from Aerodrome/Uniswap quoters,
  times stress multiplier k_dex, replenishing at rate r per step.
- Tier B, CEX-hedged: inventory-carrying liquidators who seize cbBTC and sell BTC on
  CEX. Capacity = CEX depth within (LIF-1-m) × k_cex, replenishing at r. They are
  capital-limited: cap at observed max single-day liquidated volume (~$91M) unless the
  user overrides.
- Tier C, Coinbase itself (redeem cbBTC 1:1, effectively unlimited depth at the CEX
  price): off by default; the writeup shows results with and without it, because
  whether Coinbase runs its own liquidator is unverified and matters enormously.

Queue is served largest-first (what bots do). Oracle lag L (default 1 step) delays
when a position becomes liquidatable relative to the market price.

**Outputs per (event, LLTV, max origination LTV, capacity assumptions):** liquidated
$, bad debt $ and % of supply, max queue depth, p50/p95 time-in-queue, worst step.

**Reshaping the book for other haircuts.** For LLTV' and cap', map each position's
LTV_i to LTV_i · (cap'/0.75) (borrowers draw to the same fraction of their allowance),
drop nothing. This is stated as an assumption in the writeup; sensitivity shown.

**Calibration.** Feb 5 2026 and Jun 2026 are the only events the book lived through
at scale. From Liquidate events plus Chainlink AnswerUpdated logs we get realized
latency (blocks from crossing 86% to liquidation), realized seized/repaid (= realized
bonus), liquidator concentration, and whether any liquidator address maps to a
Coinbase entity. These pin k_dex, k_cex, r and tell us if Tier C exists.

**Haircut rule for the writeup.** For each asset:
1 - LLTV >= worst N-hour move at the chosen confidence + liquidation bonus + oracle lag
move, where N is the TTL the model produces for that asset's book size against its
depth. Then max origination LTV = LLTV minus the buffer needed so that a p95
week-long drawdown does not push the median new loan into liquidation.

## 5. Repo layout

```
coinbase/
  PLAN.md
  research/            crash_table.py, notes from the three sweeps
  spine/
    fetch_positions.py   Morpho API, sliced by healthFactor bands -> data/positions_<mkt>.json
    fetch_liquidations.py  Morpho API marketTransactions -> data/liquidations_<mkt>.json
    fetch_events.py      Base getLogs (Liquidate + Chainlink AnswerUpdated) for calibration windows
    fetch_prices.py      Coinbase candles for the 7 windows -> data/prices/<event>_<asset>.csv
    fetch_depth.py       Coinbase L2 + Kraken + Aerodrome/Uniswap quoter -> data/depth.json
    tag_coinbase.py      ERC-1967 impl slot check, batched via multicall -> data/coinbase_wallets.json
    backtest.py          the model in numpy; grid over events × LLTV × cap -> data/backtest.json
    calibrate.py         realized latency/bonus/liquidator table from Feb/Jun 2026
  site/
    index.html           Plotly.js from CDN; live tab fetches Morpho + Coinbase APIs in-browser;
                         backtest/TTL tabs read data/*.json
    writeup.html         the argument, with figures from the same JSON
  .github/workflows/refresh.yml   hourly: fetch_* + backtest, commit data/, deploy Pages
```

Python 3.12, stdlib for fetching, numpy for the backtest, no framework. Static site,
no backend. Hosting: GitHub Pages (Vercel is available via MCP if you prefer).

## 6. Phases and acceptance checks

**Phase 0, repo.** `git init`, commit PLAN.md and research/. Then ultrareview has
something to review after each phase.

**Phase 1, data (1 day).** All fetchers run end to end.
Check: `python spine/fetch_positions.py` writes 39k+ debt positions whose summed
borrow is within 1% of the API's `state.borrowAssetsUsd`; `fetch_prices.py`
reproduces the table in section 2; `tag_coinbase.py` labels the two largest
borrowers as Coinbase v1.1 wallets.

**Phase 2, live dashboard (1 day).** LTV histogram, health-factor CDF, collateral-at-
risk curve, per-market cards, Coinbase-only toggle, top-N borrower table.
Check: page loads with no build step, numbers match the Morpho app market page.

**Phase 3, calibration (1 day).** Feb 5 and Jun 2-5 2026 replayed from events.
Check: `calibrate.py` reports liquidated $ within 5% of the Dune dashboard's figures
for those days, and a latency distribution in blocks.

**Phase 4, backtest + TTL (2 days).** Grid: 7 events × LLTV {62.5, 70, 77, 80, 86} ×
cap {50, 60, 70, 75} × capacity scenario {A, A+B, A+B+C}.
Check: with today's book and LLTV 86%, Feb 2026 path, A+B scenario, simulated
liquidated $ lands within 25% of the realized $170M week; bad debt in Jun 2026
scenario is 0 (as realized). If those two do not hold, the model is wrong, not the
history.

**Phase 5, writeup + publish (1 day).** Haircut recommendation per asset with the
surviving/failing grid cells, sensitivity to Tier C, and the honest list of unknowns.
Check: every number in the writeup traces to a JSON file produced by a script in the
repo.

Total: ~6 working days. Each phase is one `runner` dispatch with the acceptance check
above; `reviewer` verifies before the next phase starts.

## 6b. What changed during the build (2026-09-15)

- Phases 0-4 built and committed; Phase 5 writeup in `WRITEUP.md`, rendered at `site/writeup.html`.
- The model gained a **borrower response** term. On the exact Feb 3 2026 book, $515M of debt crossed
  86% at the trough but only $151M was liquidated: borrowers cured ~70%. Frozen-book replays
  overstate liquidations 2-3x on every lived event. Final form: a responsive share of wallets
  (deterministic hash) repays to LLTV-12pp after a reaction delay in the LLTV-6pp warning zone.
  Fit (share 0.7, delay 120 min) reproduces Oct 2025 / Feb 2026 / Jun 2026 within 15%.
- Phase 4 acceptance changed accordingly: "AB within 25% of realized" is checked on the rebuilt
  historical books with borrower response, not on today's book.
- Realized bad debt is $0.07 across nine markets (rounding dust), not exactly zero.
- Depth quoting uses hand-encoded `eth_call` (no `cast` dependency); size grids extended and
  capacity values carry a `saturated` flag when the largest quoted size still fits.
- Runners die on commands over ~10 minutes; every long script takes `--max-seconds` and resumes.

## 7. Decisions I made (say so if you want them changed)

- Static site + hourly cron, not a server. Both APIs are CORS-open; a backend adds
  nothing.
- No paid historical depth. Live depth × documented stress multipliers (Kaiko:
  >90% top-of-book collapse Oct 2025; roughly halved after FTX). Sensitivity shown.
- Backtests run against today's book reshaped by haircut, not a reconstructed
  historical book, for pre-launch events (the book did not exist). For Oct 2025,
  Feb 2026, Jun 2026 we reconstruct the actual book from events.
- Cover all nine markets in the dashboard, but the backtest and haircut argument go
  deep on cbBTC and WETH (98% of the book) and use CEX-only depth for the alts.
- Coinbase-only filter via implementation-slot check, batched through multicall,
  cached; not a Dune dependency.

## 8. Open questions worth your answer before Phase 4

1. Does Coinbase liquidate its own book? If you know, or can find out, it changes the
   headline. Otherwise the writeup carries both scenarios.
2. Audience for the writeup: Coinbase/Morpho risk people, or a public "here is what
   the data says" post? Changes tone and how hard the recommendation is worded.
3. Hosting: GitHub Pages (default) or Vercel.

## 9. Brainstorm: extensions worth doing later, not now

- Liquidator leaderboard with per-address latency and profit; flag Coinbase-affiliated
  addresses.
- Live "distance to bad debt" gauge: how far price must fall before the queue exceeds
  capacity, updated each block.
- Supplier-side view: which vaults fund the market and what bad debt would do to them.
- Chainlink deviation/heartbeat replay to quantify oracle lag per event.
- Alert bot (Telegram) when collateral-at-risk within 10% exceeds modeled capacity.
- Compare Coinbase's 86% with Aave cbBTC on Base (73/78/7.5%) and TradFi lenders
  (Ledn 50/70/80, Unchained 40-50/67/83) in the writeup's framing.
