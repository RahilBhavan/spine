# What haircut should Coinbase take on BTC and ETH collateral?

*Spine, 2026-09-19. Every number here is produced by a script in this repo from public data: the Morpho API, Base RPC, Coinbase Exchange, and Chainlink logs. Tables are printed by `spine/writeup_tables.py` and `spine/caps.py` from `data/backtest.json`, `data/calibration.json`, `data/summary.json`, `data/depth.json` and `data/caps.json`. The dashboard refreshes hourly.*

## The short version

**Scope of the book figures.** The replay ran on the cbBTC/USDC market's loan book as of 2026-09-19, the book `latest_book` points to in `data/backtest.json`; the writeup is dated the same day. Every percentage of supply below is of that book's $1.58B of USDC supplied. The $1.41B of debt, $2.86B of collateral and 39,000 positions below are for the cbBTC/USDC market only, as of 2026-09-19 (the 2026-09-19 19:56 UTC snapshot reads $1.43B and 39,554 positions for cbBTC; the writeup text was written earlier that day). The README's book figures are a different book: all nine markets, from a later snapshot (2026-09-23 19:05 UTC: $1.63B borrowed, 68,772 positions, of which cbBTC is $1.46B and 40,075). The 97.5% Coinbase Smart Wallet share is the all-market borrow share; cbBTC alone reads 97.4%.

Coinbase's app routes USDC loans against cbBTC and ETH to Morpho markets on Base, funded by Morpho vault suppliers, at an 86% liquidation LTV with a 4.38% liquidation bonus. The book is $1.41B of debt against $2.86B of cbBTC, 39,000 positions, 97.5% of it Coinbase Smart Wallets. It has been through three real stress events (Oct 2025, Feb 2026, Jun 2026), cleared $256M of liquidations in the four stress weeks alone, and taken zero bad debt.

That record is real and it is also not the test. The lived events gave borrowers hours to days of warning before liquidation; March 2020 gave 25 minutes. Replaying today's book through seven crash paths, with liquidators and borrowers behaving the way the lived events show they behave, two separate measures matter for each path. *Loss by end of path* is what lenders lost once the price had bounced. *Supply left unserved at the trough* is how much of the book sat underwater at the lowest print with no liquidator able to act, and it would become a loss if the price did not bounce. They are taken at different moments and are reported separately throughout, never as one comparison.

| Collateral | Today (LLTV / max draw) | Recommended | Why |
|---|---|---|---|
| cbBTC | 86% / 75% | **A committed backstop liquidator first; then 80% / 66-70%** | March 2020 replay at 86%. Loss by end of path: $9.2M (0.6% of supply). Supply left unserved at the trough, a separate measure: $158.4M (10.0%). Cutting the LLTV alone does little to the unserved measure (77%: 8.4%), because liquidator capital, not the haircut, is what binds. Tripling liquidator capital takes it to 6.2%. A Coinbase backstop leaves $0 unserved and $13.1M (0.8%) realized loss. At 80% every other path is clean |
| WETH | 86% / 75% | **77% / 70%** | ETH gaps more than the 4.38% bonus inside five minutes; at 86% three of seven paths leave bad debt even with unlimited depth. At 77% none do. cbETH already sits at 77% |
| cbXRP, SOL, cbDOGE, cbADA, cbLTC, JitoSOL | 62.5% / 55% | **62.5%**, max draw 47%, plus a per-asset book cap tied to Coinbase's own order-book depth | The 26-point buffer to the bad-debt line covers the worst observed 4-hour moves (-31% to -37%); the p95 weekly drawdown rule puts the cap at 46-48%. The constraint is disposal: none of these have a venue on Base |

Three things the replay makes clear. First, bots are fast and they close positions in full; the binding constraint on a Black Thursday path is how much capital they can deploy in a day, and the only measurement of that is a day when it did not bind. Second, the LLTV is the right lever among the parameters Coinbase controls, because on Morpho a lower LLTV also raises the liquidation bonus (at 86% a liquidated position is underwater after a further 10.2% drop, at 80% after 14.9%, at 77% after 17.3%), but it moves the realized loss by single-digit millions and the trough exposure by a point of supply. Third, the margin-call flow that protects borrowers in slow crashes cannot act in 20 minutes, which is why the recommendation includes draining the queue during the slide rather than at the cliff.

## 1. What the book looks like

- cbBTC/USDC 86%: $1.413B borrowed, $2.860B collateral, utilization 90%, borrow APY 4.8%. Book LTV 49%; most debt sits between 40% and 65% LTV. Largest position $5.2M.
- Eight more Coinbase markets (WETH 86%, cbETH 77%, six alts at 62.5%) add $154M. WETH is the only one that matters for size ($83M).
- A -10% instantaneous move puts $30M of debt over the 86% line; -20%, $112M; -30%, $336M. Morpho's own Dune dashboard shows the same curve and puts $1.1B of collateral at risk at -50%.
- Realized bad debt across all nine markets since inception: $0.07, rounding dust.

## 2. Who liquidates it, and how

From every liquidation in the three lived events, valued at the Chainlink price in the liquidation block:

| Window | cbBTC liquidations | Repaid | Seized | Bonus (p50) | Latency p50 / p90 | Within 60s | Liquidators | Top share |
|---|---|---|---|---|---|---|---|---|
| Oct 9-12 2025 | 410 | $17.6M | $18.4M | 4.38% | 4s / 70s | 90% | 21 | 23% |
| Feb 2-8 2026 | 4,116 | $150.8M | $157.4M | 4.38% | 2s / 88s | 87% | 46 | 16% |
| Jun 1-7 2026 | 3,308 | $72.1M | $75.3M | 4.38% | 0s / 6s | 97% | 110 | 11% |
| Jun 23-27 2026 | 394 | $15.4M | $16.0M | 4.38% | 0s / 6s | 98% | 43 | 23% |

Latency is measured from the oracle update that pushed the position over 86% to the liquidation transaction. Bots are not the bottleneck. Every top-10 liquidator is a contract; the field is competitive (no address above a quarter of volume). And they close positions: 80-94% of liquidations repaid the whole debt (a first cut of this analysis counted 28-50% because a few dust shares survive a full close; measured by debt repaid, the median "partial" liquidation repaid 99.99%). The model closes in full.

Peak throughput on Feb 5 2026: $11.2M repaid in the busiest five minutes, $32.6M in the busiest hour, $96.8M in the day ($101M of collateral seized). Coinbase's BTC-USD bid book within 4.38% of mid has ranged from $19M to $35M across the hourly snapshots of the past three days; on-chain cbBTC-to-USDC capacity at 4.38% slippage on Base is $3.5-4.4M across every Aerodrome and Uniswap pool. The busiest day is the only measurement we have of how much capital liquidators bring. It was not a binding day (everything that became liquidatable was cleared within seconds), so it is a floor on their capacity, not an estimate of it.

## 3. Borrowers respond, and it is not enough on a cliff

Take the exact cbBTC book on Feb 3 2026 ($1,075M debt, rebuilt from every transaction) and mark it at the Feb 6 trough ($60,001): $515M of debt crosses 86%. Only $151M was liquidated. Borrowers cured about 70% of at-risk debt by topping up or repaying while Coinbase's margin warnings fired.

We model this as a responsive share of borrowers who repay to 74% LTV once they have spent a reaction time inside the 80-86% warning zone. Fitting the share and the delay on the three cbBTC events gives 70% responsive with a two-hour reaction, reproducing realized liquidation volume at 0.85–0.99x on all three (Feb 0.99x, Jun 0.85x, Oct 0.95x). Held-out WETH comes in at 1.58x and 0.85x. Without borrower response the same model overstates the three events by 2.0x, 2.9x and 1.7x. The fit is a plateau (60-70% responsive, one to two hours all fit about equally), so read those as ranges: on March 2020 the four cells (60% / 1 h, 60% / 2 h, 70% / 1 h, 70% / 2 h) give a loss by end of path of $9.1M, $9.1M, $9.0M and $9.2M, and, as a separate measure, supply left unserved at the trough of $150.2M, $159.5M, $147.3M and $158.4M. Two parameters on three events deserves modest confidence and the share absorbs whatever else the model lacks. The ranking of effects is robust.

What the fit buys is time-dependence. Median time between entering the 80-86% zone and crossing 86%, for positions that ended up liquidated:

| Crash | Warning time for the median liquidated position |
|---|---|
| Aug 2024 | 48 h |
| Jun 2026 | 35 h |
| Feb 2026 | 22 h |
| FTX Nov 2022 | 14 h |
| May 2021 | 4 h |
| Oct 2025 | 2 h |
| **Mar 2020** | **25 min** |

Coinbase's borrower-warning flow works because crashes so far have been slow. On the March 2020 shape it cuts liquidations from $997.9M to $618.3M but leaves realized bad debt where it was ($10.9M with no response, $9.2M fitted, $5.5M if 90% of borrowers reacted within 15 minutes). Borrowers can save themselves in a slow crash; in a fast one only liquidators can save the lenders.

## 4. The backtest

Today's cbBTC book is dropped onto each historical path from its pre-crash peak at 5-minute resolution. Positions over LLTV enter a queue served largest-first and closed in full. Liquidator capacity per step comes from measured depth read 1% inside the bonus, times a stress multiplier (DEX 0.5, CEX 0.3), with 20% replenishment per step. Exchange-hedged liquidators are also limited by capital: a rolling 24-hour cap set by default to the most collateral the book has ever seen seized in a day ($101M, Feb 5 2026) and varied below. Loss is the shortfall realized on liquidations plus what is still underwater (LTV above 1/LIF, 95.8% at 86%) at the end of the path. Exposure is the same quantity marked at the lowest oracle print. Three capacity scenarios:

- **A**: on-chain bots only (Base DEX depth).
- **AB**: plus liquidators who seize cbBTC and sell BTC on Coinbase and Kraken. This matches observed behaviour.
- **ABC**: plus Coinbase itself redeeming cbBTC 1:1, effectively unlimited depth and capital at the exchange price. Nothing public says this exists: Morpho's launch post says liquidation works "without requiring Coinbase's direct involvement", Coinbase's help center says it cannot prevent liquidation, and the top liquidators on the market are independent bots that sell seized cbBTC on Uniswap in the same transaction (`research/self_liquidation.md`). ABC is what a commitment would buy.

cbBTC at today's terms (86% / 75%), fitted behaviour:

| Path | Worst 4h / 24h | AB: liquidated | AB: loss by end of path | AB: left unserved at trough | AB: queue p50 / p95 | ABC: loss by end of path | ABC: left unserved at trough |
|---|---|---|---|---|---|---|---|
| Mar 2020 | -35% / -50% | $618.3M | **$9.2M (0.6%)** ($8.3M-$9.2M) | **$158.4M (10.0%)** | 2.0 days / 3.3 days | $13.1M (0.8%) | 0 |
| May 2021 | -26% / -32% | $356.5M | $0.28M (0.0%) ($0.11M-$0.45M) | $17.1M (1.1%) | 11 h / 4.1 days | $0.73M (0.0%) | 0 |
| FTX Nov 2022 | -15% / -19% | $64.6M | 0 | 0 | 0 min / 10 min | 0 | 0 |
| Aug 2024 | -11% / -20% | $81.5M | 0 | 0 | 0 min / 6 h | 0 | 0 |
| Oct 2025 | -10% / -13% | $18.0M | 0 | 0 | 0 min / 0 min | 0 | 0 |
| Feb 2026 | -9% / -18% | $94.6M | 0 | 0 | 0 min / 5 min | 0 | 0 |
| Jun 2026 | -7% / -9% | $25.7M | 0 | 0 | 0 min / 0 min | 0 | 0 |

Percentages are of the $1.58B USDC supplied to the market in the 2026-09-19 book; the range in brackets is the loss over ten reshuffles of which wallets are responsive. Loss by end of path and supply left unserved at the trough are different measures taken at different moments, not a before and after of one number. Under ABC nothing is left unserved, so its only trough figure is the $13.1M shortfall already counted as loss. Bad debt on Morpho is socialized to suppliers, which includes depositors in the Coinbase USDC lending product, not Coinbase's balance sheet.

The March 2020 row is the whole argument. By the end of the path the loss is 0.6% of supply, because BTC bounced from $3,858 to over $5,000 within hours and the queue was served above water on the way back up. Measured separately, at the low 10.0% of supply was left unserved, underwater with a queue of two days. Under the backstop scenario the queue is served at the low itself, which realizes the oracle-jump shortfall ($13.1M, 0.8% realized loss) and leaves $0 unserved. The bounce, not the lender, decided how much of the unserved measure became loss.

What moves each measure. Scenario AB, March 2020, as two separate tables:

| LLTV: loss by end of path | Capital as observed ($101.1M/day) | 3x | 10x | Depth-limited only |
|---|---|---|---|---|
| 86% | $9.2M (0.6%) | $2.2M (0.1%) | $2.1M (0.1%) | $2.1M (0.1%) |
| 80% | $4.0M (0.3%) | $0.70M (0.0%) | $1.2M (0.1%) | $1.2M (0.1%) |
| 77% | $2.4M (0.2%) | $1.1M (0.1%) | $1.5M (0.1%) | $1.5M (0.1%) |

| LLTV: left unserved at the trough | Capital as observed ($101.1M/day) | 3x | 10x | Depth-limited only |
|---|---|---|---|---|
| 86% | $158.4M (10.0%) | $97.7M (6.2%) | $75.2M (4.7%) | $75.2M (4.7%) |
| 80% | $143.0M (9.0%) | $91.8M (5.8%) | $54.1M (3.4%) | $54.1M (3.4%) |
| 77% | $133.5M (8.4%) | $88.7M (5.6%) | $38.0M (2.4%) | $38.0M (2.4%) |

Read down a column of the unserved table: the LLTV buys about a point of supply from 86% to 80% and half a point from 80% to 77%. Read across a row: tripling liquidator capital buys three to four points, and unlimited capital five to six. The loss table moves by tenths of a point either way. At 70% and 62.5% LLTV (with a 60% max draw) the supply left unserved falls to $25-28M and the realized loss to rounding dust, but that is a different product. On May 2021 the supply left unserved is $17.1M (1.1%) at 86% and under $2M from 80% down, at any capital level.

What turns the unserved measure into loss is the bounce. To see what a slower recovery costs, the same paths are replayed with the trough low held for an hour and for a day before the historical bounce resumes:

| Path | LLTV | Loss, no hold | Loss, held 1 h | Loss, held 1 day |
|---|---|---|---|---|
| Mar 2020 | 86% | $9.2M (0.6%) | $9.7M (0.6%) | $38.1M (2.4%) |
| Mar 2020 | 80% | $4.0M (0.3%) | $4.6M (0.3%) | $29.7M (1.9%) |
| Mar 2020 | 77% | $2.4M (0.2%) | $2.6M (0.2%) | $26.0M (1.6%) |
| May 2021 | 86% | $0.28M (0.0%) | $0.59M (0.0%) | $5.3M (0.3%) |
| May 2021 | 80% | 0 | 0 | $0.20M (0.0%) |
| May 2021 | 77% | 0 | 0 | $0.00M (0.0%) |

An hour at the low changes little; a day at the low quadruples the March 2020 loss at 86% and shrinks what the LLTV buys in relative terms (cutting 86% to 77% removes three-quarters of the loss with no hold, a third after a day at the low), because the queue is then served at the low and liquidator capital decides how much of the exposure is realized.

Whether bots trim positions instead of closing them (trim to 74%, which on Morpho means repaying about two-thirds of the debt), the exchange-depth multiplier, a volatility-driven depth collapse, and the hash seed that decides which wallets are responsive each move these results by a few percent and are in `data/backtest.json`. The depth-collapse term was anchored on Kaiko's Oct 10 2025 measurement and turned off by default because it under-predicts the liquidations that actually happened that day by 40%.

WETH at 86% / 75%: March 2020 $0.93-1.1M, May 2021 $0.25M, Aug 2024 $0.15M of loss across scenarios (about 1.1% of that market's $94M supply at worst), because ETH gaps more than 4.38% inside five minutes and a backstop that liquidates everything instantly realizes the gap. At 80%, $0.13-0.21M on March 2020 and $0.02M on May 2021; at 77%, every path is clean under every scenario.

## 4b. Stress grid: crash path x LLTV x liquidator capital

*Every figure in this section comes from `python -m spine.stress_grid`, which writes `data/stress_grid.csv` (140 rows: seven paths x four LLTVs x five capital levels), and the tables are printed by `python -m spine.stress_grid --table`. Each row carries its book date in the first column. The loan book is the cbBTC/USDC book fetched on **2026-10-22** (supply $1,780M, 42,678 positions with debt); depth is the 2026-09-23 snapshot in `data/depth.json`; the borrower response is the stored fit (70% responsive, 2 h) and the scenario is AB. This is a later book than the one section 4 ran on (2026-09-19, $1.58B supply), so the March 2020 / 86% cell reads differently here, not because the model changed.*

The cbBTC book is replayed on all seven paths at LLTV 86%, 80% and 77% (draw cap 75%) and 70% (cap 60%, as in the LLTV grid in section 4), against five levels of liquidator capital: the Tier B rolling-24h cap at 0.5x, 1x, 3x and 10x the most collateral seized in one day ($101.1M, Feb 5 2026), and unlimited, where only depth limits. Two measures stay in separate columns and are never added or compared as one number:

- **Underwater and unserved at trough**: debt still alive and underwater at the lowest oracle print, plus the shortfall already realized by then (the "exposure at trough" of section 4). What the lenders are exposed to if the price does not bounce.
- **Realized loss**: shortfall realized on liquidations by the end of the replayed path, after the historical bounce. Shortfall still underwater at the end of the path is not in this column; it is in the CSV as `underwater_at_end_usd` (zero in every cell of the tables below).

Percentages are of the book's supply. **Binds first** is the limit at the first five-minute step, counted from the start of the path (the pre-trough peak), where the queue could not be served in full: *depth* is the per-step replenishing DEX and CEX capacity, *capital* is the Tier B rolling-24h cap setting that step's capacity, *oracle gap* is the market already below the oracle by more than the liquidation bonus so nobody liquidates at a profit, *none* is a queue served in full at every step. "Capital cap from N h" is the first such step where the cap was the limit. It is a chronological marker, not a share of the loss: depth binds first in most cells (capacity refills 20% of its base per step), and the capital cap matters later.

| Book date | Crash path | LLTV / cap | Liquidator capital per day | Underwater and unserved at trough | Realized loss | Binds first |
|---|---|---|---|---|---|---|
| 2026-10-22 | Mar 2020 | 86% / 75% | $50.5M (0.5x) | $227.3M (12.8%) | $27.1M (1.5%) | oracle gap at 114.0 h; capital cap from 114.8 h |
| 2026-10-22 | Mar 2020 | 86% / 75% | $101.1M (1x) | $213.2M (12.0%) | $22.4M (1.3%) | oracle gap at 114.0 h; capital cap from 115.8 h |
| 2026-10-22 | Mar 2020 | 86% / 75% | $303.3M (3x) | $154.5M (8.7%) | $8.4M (0.5%) | oracle gap at 114.0 h; capital cap from 120.1 h |
| 2026-10-22 | Mar 2020 | 86% / 75% | $1011.0M (10x) | $66.2M (3.7%) | $2.7M (0.2%) | oracle gap at 114.0 h |
| 2026-10-22 | Mar 2020 | 86% / 75% | unlimited | $66.2M (3.7%) | $2.7M (0.2%) | oracle gap at 114.0 h |
| 2026-10-22 | Mar 2020 | 80% / 75% | $50.5M (0.5x) | $199.6M (11.2%) | $15.5M (0.9%) | depth at 0.2 h; capital cap from 114.2 h |
| 2026-10-22 | Mar 2020 | 80% / 75% | $101.1M (1x) | $186.5M (10.5%) | $9.4M (0.5%) | depth at 0.2 h; capital cap from 115.2 h |
| 2026-10-22 | Mar 2020 | 80% / 75% | $303.3M (3x) | $137.5M (7.7%) | $3.7M (0.2%) | depth at 0.2 h; capital cap from 119.0 h |
| 2026-10-22 | Mar 2020 | 80% / 75% | $1011.0M (10x) | $31.6M (1.8%) | $0.67M (0.0%) | depth at 0.2 h; capital cap from 133.2 h |
| 2026-10-22 | Mar 2020 | 80% / 75% | unlimited | $31.6M (1.8%) | $0.67M (0.0%) | depth at 0.2 h |
| 2026-10-22 | Mar 2020 | 77% / 75% | $50.5M (0.5x) | $178.3M (10.0%) | $9.1M (0.5%) | depth at 0.2 h; capital cap from 0.7 h |
| 2026-10-22 | Mar 2020 | 77% / 75% | $101.1M (1x) | $166.1M (9.3%) | $4.2M (0.2%) | depth at 0.2 h; capital cap from 115.2 h |
| 2026-10-22 | Mar 2020 | 77% / 75% | $303.3M (3x) | $123.5M (6.9%) | $1.3M (0.1%) | depth at 0.2 h; capital cap from 118.7 h |
| 2026-10-22 | Mar 2020 | 77% / 75% | $1011.0M (10x) | $16.6M (0.9%) | $0.25M (0.0%) | depth at 0.2 h; capital cap from 132.4 h |
| 2026-10-22 | Mar 2020 | 77% / 75% | unlimited | $16.6M (0.9%) | $0.25M (0.0%) | depth at 0.2 h |
| 2026-10-22 | Mar 2020 | 70% / 60% | $50.5M (0.5x) | $50.2M (2.8%) | $0.01M (0.0%) | depth at 114.1 h; capital cap from 114.3 h |
| 2026-10-22 | Mar 2020 | 70% / 60% | $101.1M (1x) | $46.8M (2.6%) | $0.02M (0.0%) | depth at 114.1 h; capital cap from 115.1 h |
| 2026-10-22 | Mar 2020 | 70% / 60% | $303.3M (3x) | $19.1M (1.1%) | 0 | depth at 114.1 h; capital cap from 118.2 h |
| 2026-10-22 | Mar 2020 | 70% / 60% | $1011.0M (10x) | $2.2M (0.1%) | 0 | depth at 114.1 h |
| 2026-10-22 | Mar 2020 | 70% / 60% | unlimited | $2.2M (0.1%) | 0 | depth at 114.1 h |
| 2026-10-22 | May 2021 | 86% / 75% | $50.5M (0.5x) | $24.1M (1.4%) | 0 | oracle gap at 67.9 h; capital cap from 68.5 h |
| 2026-10-22 | May 2021 | 86% / 75% | $101.1M (1x) | $20.1M (1.1%) | 0 | oracle gap at 67.9 h; capital cap from 224.7 h |
| 2026-10-22 | May 2021 | 86% / 75% | $303.3M (3x) | $18.6M (1.0%) | $0.10M (0.0%) | oracle gap at 67.9 h |
| 2026-10-22 | May 2021 | 86% / 75% | $1011.0M (10x) | $18.6M (1.0%) | $0.10M (0.0%) | oracle gap at 67.9 h |
| 2026-10-22 | May 2021 | 86% / 75% | unlimited | $18.6M (1.0%) | $0.10M (0.0%) | oracle gap at 67.9 h |
| 2026-10-22 | May 2021 | 80% / 75% | $50.5M (0.5x) | $3.1M (0.2%) | 0 | depth at 67.9 h; capital cap from 68.2 h |
| 2026-10-22 | May 2021 | 80% / 75% | $101.1M (1x) | $1.7M (0.1%) | 0 | depth at 67.9 h; capital cap from 223.5 h |
| 2026-10-22 | May 2021 | 80% / 75% | $303.3M (3x) | $0.67M (0.0%) | 0 | depth at 67.9 h |
| 2026-10-22 | May 2021 | 80% / 75% | $1011.0M (10x) | $0.67M (0.0%) | 0 | depth at 67.9 h |
| 2026-10-22 | May 2021 | 80% / 75% | unlimited | $0.67M (0.0%) | 0 | depth at 67.9 h |
| 2026-10-22 | May 2021 | 77% / 75% | $50.5M (0.5x) | $1.0M (0.1%) | 0 | depth at 1.3 h; capital cap from 15.8 h |
| 2026-10-22 | May 2021 | 77% / 75% | $101.1M (1x) | $0.41M (0.0%) | 0 | depth at 1.3 h; capital cap from 223.5 h |
| 2026-10-22 | May 2021 | 77% / 75% | $303.3M (3x) | $0.00M (0.0%) | 0 | depth at 1.3 h |
| 2026-10-22 | May 2021 | 77% / 75% | $1011.0M (10x) | $0.00M (0.0%) | 0 | depth at 1.3 h |
| 2026-10-22 | May 2021 | 77% / 75% | unlimited | $0.00M (0.0%) | 0 | depth at 1.3 h |
| 2026-10-22 | May 2021 | 70% / 60% | $50.5M (0.5x) | 0 | 0 | depth at 68.0 h; capital cap from 68.2 h |
| 2026-10-22 | May 2021 | 70% / 60% | $101.1M (1x) | 0 | 0 | depth at 68.0 h; capital cap from 224.8 h |
| 2026-10-22 | May 2021 | 70% / 60% | $303.3M (3x) | 0 | 0 | depth at 68.0 h |
| 2026-10-22 | May 2021 | 70% / 60% | $1011.0M (10x) | 0 | 0 | depth at 68.0 h |
| 2026-10-22 | May 2021 | 70% / 60% | unlimited | 0 | 0 | depth at 68.0 h |
| 2026-10-22 | FTX Nov 2022 | 86% / 75% | $50.5M (0.5x) | 0 | 0 | depth at 88.2 h; capital cap from 108.4 h |
| 2026-10-22 | FTX Nov 2022 | 86% / 75% | $101.1M (1x) | 0 | 0 | depth at 88.2 h |
| 2026-10-22 | FTX Nov 2022 | 86% / 75% | $303.3M (3x) | 0 | 0 | depth at 88.2 h |
| 2026-10-22 | FTX Nov 2022 | 86% / 75% | $1011.0M (10x) | 0 | 0 | depth at 88.2 h |
| 2026-10-22 | FTX Nov 2022 | 86% / 75% | unlimited | 0 | 0 | depth at 88.2 h |
| 2026-10-22 | FTX Nov 2022 | 80% / 75% | $50.5M (0.5x) | 0 | 0 | depth at 88.2 h; capital cap from 88.2 h |
| 2026-10-22 | FTX Nov 2022 | 80% / 75% | $101.1M (1x) | 0 | 0 | depth at 88.2 h |
| 2026-10-22 | FTX Nov 2022 | 80% / 75% | $303.3M (3x) | 0 | 0 | depth at 88.2 h |
| 2026-10-22 | FTX Nov 2022 | 80% / 75% | $1011.0M (10x) | 0 | 0 | depth at 88.2 h |
| 2026-10-22 | FTX Nov 2022 | 80% / 75% | unlimited | 0 | 0 | depth at 88.2 h |
| 2026-10-22 | FTX Nov 2022 | 77% / 75% | $50.5M (0.5x) | 0 | 0 | capital at 88.2 h; capital cap from 88.2 h |
| 2026-10-22 | FTX Nov 2022 | 77% / 75% | $101.1M (1x) | 0 | 0 | depth at 88.2 h |
| 2026-10-22 | FTX Nov 2022 | 77% / 75% | $303.3M (3x) | 0 | 0 | depth at 88.2 h |
| 2026-10-22 | FTX Nov 2022 | 77% / 75% | $1011.0M (10x) | 0 | 0 | depth at 88.2 h |
| 2026-10-22 | FTX Nov 2022 | 77% / 75% | unlimited | 0 | 0 | depth at 88.2 h |
| 2026-10-22 | FTX Nov 2022 | 70% / 60% | $50.5M (0.5x) | 0 | 0 | none |
| 2026-10-22 | FTX Nov 2022 | 70% / 60% | $101.1M (1x) | 0 | 0 | none |
| 2026-10-22 | FTX Nov 2022 | 70% / 60% | $303.3M (3x) | 0 | 0 | none |
| 2026-10-22 | FTX Nov 2022 | 70% / 60% | $1011.0M (10x) | 0 | 0 | none |
| 2026-10-22 | FTX Nov 2022 | 70% / 60% | unlimited | 0 | 0 | none |

Reading the Mar 2020 rows (book 2026-10-22):

- At 86% and the observed capital, $213.2M (12.0%) is underwater and unserved at the trough and $22.4M (1.3%) is realized by the end of the path. With 3x the capital the two read $154.5M (8.7%) and $8.4M (0.5%); with 10x or unlimited capital, $66.2M (3.7%) and $2.7M (0.2%). Capital moves both columns at every LLTV.
- Lowering the LLTV at the observed capital moves the unserved column from 12.0% (86%) to 10.5% (80%), 9.3% (77%) and 2.6% (70% / 60%); the realized column from 1.3% to 0.5%, 0.2% and 0.0%.
- At 86% the first binding limit is the oracle gap at 114.0 h at every capital level; at 80% and 77% it is depth at 0.2 h; at 70% / 60% it is depth at 114.1 h. The capital cap is the limit from 115-120 h at 1x and 3x. At 10x it is reached only at 80% (133.2 h) and 77% (132.4 h) and at unlimited capital never.
- May 2021 at 86% / 75% leaves $20.1M (1.1%) unserved and no realized loss at the observed capital. At 77% it is $0.41M, and under $0.5M from there down, at the observed capital. FTX Nov 2022 has nothing underwater at the trough and nothing realized in any of its 20 cells, though a limit binds in all 15 cells at 86%, 80% and 77% (depth in 14, capital in the 0.5x cell at 77%) and in none at 70% / 60%.

The other four paths (Aug 2024, Oct 2025, Feb 2026, Jun 2026) read zero on both measures in all 80 cells. The binding column still differs: Oct 2025 and Jun 2026 are *none* everywhere, Aug 2024 is *depth* in every cell, Feb 2026 is *capital* in 4 cells, *depth* in 12 and *none* in 4. Their rows are in `data/stress_grid.csv`.

Reproducing the earlier result. The section 4 headline (Mar 2020, 86% / 75%, AB, observed capital: 10.0% unserved, $158.4M, and $9.2M realized) was run on the 2026-09-19 book. That book is not in the repository (`data/positions_*.json` is untracked and the `data` branch keeps only the latest snapshot), nor is the depth snapshot of that hour, so the figure cannot be regenerated here. What the script checks instead: the baseline cell is replayed twice and must agree exactly; it is then compared with the `data/backtest.json` run for the same book date if one exists (none exists for 2026-10-22, and the script says so); and, as a one-off check rather than a test, the instrumented simulator and the unmodified one gave identical values in every output field of all 140 cells. The baseline on the 2026-10-22 book reads 12.0% unserved ($213.2M) and 1.3% realized ($22.4M).

## 5. What the origination cap should be

The liquidation LTV protects lenders; the origination cap protects borrowers from being liquidated by an ordinary bad week. The rule: a loan drawn at the cap should stay below LLTV after a p95 seven-day drawdown, so cap = LLTV × (1 − dd7_p95).

| Asset | 7-day drawdown p95 / p99, since 2020 | Since 2023 | Cap at current LLTV (p95, 2020+) | Cap at 80% LLTV | Today's max draw |
|---|---|---|---|---|---|
| BTC | 17.1% / 28.6% | 12.7% / 19.5% | 71% | 66% | 75% |
| ETH | 22.9% / 36.0% | 19.5% / 29.6% | 66% (86%), 59% (77%) | 62% | 75% |
| XRP | 23.8% / 45.5% | 22.9% / 37.5% | 48% | | 55% |
| SOL | 24.8% / 42.1% | 22.4% / 32.3% | 47% | | 55% |
| DOGE, ADA, LTC | 25-26% / 38-41% | 23-24% / 31-36% | 46-47% | | 55% |

Coinbase's 75% max draw on BTC and ETH exceeds the p95 rule on the full history; it is right on it if only post-2022 history counts. The alts' 55% is eight points above their p95 caps. None of this is a lender-loss argument; it is a "how often do your customers get liquidated by a normal week" argument, and it says the caps are set for the post-2022 regime.

RiskDAO's SmartLTV formula (LTV = exp(−c·σ/√(l/d)) − β, with l the liquidity inside the bonus and d the borrow) is a useful cross-check because it fails loudly: for cbBTC it returns 0.9% at its mildest calibration and negative at the others. With $44M of measured bids inside the 4.38% bonus against a $1.42B book, the formula is saying the book is thirty times too large for the liquidity at the bonus, not that the LLTV is wrong. That is the same finding as section 4 from a different direction.

## 6. The argument, in one line per asset

The rule: **1 − LLTV must cover the worst move over the time it takes to clear the queue, plus the liquidation bonus, plus one oracle interval.** Basel's SCO60.29 says the same thing in regulator language: assess the liquidation period and downturn liquidity depth before recognizing crypto collateral.

**cbBTC.** On a March 2020 path the queue takes two days to clear at the median with the capital liquidators brought on Feb 5 2026, and BTC fell 58% peak to trough over that week. No LLTV covers that: 77% still leaves 8.4% of supply unserved at the low. What does: a backstop liquidator that can redeem cbBTC and sell BTC on Coinbase's own book (the ABC columns: $13.1M (0.8%) realized loss at 86%, zero at 77%, $0 left unserved). Only Coinbase can be that liquidator, nothing public says it is, and USDC suppliers are lending as if the answer were known; then the LLTV, where 80% costs 0.3% realized loss and leaves 9.0% unserved on the worst path and is clean everywhere else. The origination cap follows from section 5: 66% at 80% LLTV on the full history, 70% if only the post-2022 regime counts. Comparators, in the same three numbers (how much you can draw, where the warning starts, where you are liquidated):

| Lender | Max draw | Warning / margin call | Liquidation | Penalty | Cure period |
|---|---|---|---|---|---|
| Coinbase on Morpho (cbBTC, today) | 75% | 80% (model's warning zone) | 86% | 4.38% bonus | none; bots act in seconds |
| Coinbase on Morpho (recommended) | 66-70% | 80% pre-liquidation band | 80% | 6.38% at 80% (Morpho's LIF rises as LLTV falls) | pre-liquidation drains the queue on the slide |
| Aave v3 on Base (cbBTC) | 73% | none | 78% | 7.5% | none |
| Ledn | 50% | 70% | 80% | undisclosed | margin call, no fixed window |
| Unchained | 40-50% | 67% | 83% | undisclosed | 24 hours |
| SALT | 70% | 75% | 83.33% | undisclosed | margin call |

Coinbase's 86% is the highest liquidation line in the set and its 11-point gap from draw to liquidation is the narrowest after SALT; every comparator that lends at a similar line either liquidates at a wider penalty (Aave) or gives itself a human cure window (Unchained), which is the TradFi form of the pre-liquidation band above. Sources in `research/sources_prior_art.md`.

**Pre-liquidation, whichever LLTV is chosen.** Morpho supports pre-liquidation contracts: a band (say 80-86% LTV) where positions can be partially closed at a small bonus (1-2%) before the hard line. On a slow slide it drains the queue while capacity is idle. It costs borrowers less than a 4.38% liquidation and it is the on-chain form of the margin call Coinbase already sends.

**WETH.** 77%. Same as Coinbase already uses for cbETH, and the only setting in the grid that survives all seven paths under every scenario. The cost is small: the market is $83M. Cap 59-62% by the p95 rule.

**Alts at 62.5%.** The volatility buffer is adequate: the bad-debt line is a further 29.6% below the liquidation line, and the worst observed 4-hour moves are -31% (XRP, Mar 2020), -35% (XRP, Oct 2025), -37% (DOGE, Oct 2025), -34% (SOL, FTX). The max draw should come down from 55% to the p95 cap of 46-48%. What is missing is a size rule. There is no on-chain venue for cbXRP, cbDOGE, cbADA or cbLTC on Base; every seized unit must be redeemed through Coinbase and sold on Coinbase's book, which holds $8-10M of XRP or SOL bids within 10% of mid against a 12.7% bonus. The per-asset cap: debt that would be liquidatable at -30% must not exceed one hour of Coinbase's own depth (one hour of Tier B collateral capacity at 62.5%, converted to debt at the bonus). Today's distribution: cbXRP has $10.7M liquidatable at -30% against a one-hour cap of $20.9M (1.9x headroom); SOL $1.4M against $29.0M (20.2x). Drawn to the 55% max draw, the whole book is liquidatable at -30% (55/0.70 = 78.6% > 62.5%), so the cap is $20.9M of debt for cbXRP and $29.0M for SOL; today's books are $48.7M and $5.5M. cbXRP is already past it and is the one to watch. Replaying the two alt books with data (cbXRP, SOL) at 62.5% / 55% against Coinbase depth alone:

| cbXRP (supply $54M) | AB: liquidated | AB: loss by end of path | AB: left unserved at trough | AB: queue p95 |
|---|---|---|---|---|
| Mar 2020 | $32.3M | 0 | 0 | 11 h |
| Aug 2024 | $7.8M | 0 | 0 | 50 min |
| Oct 2025 | $9.8M | 0 | 0 | 75 min |
| Feb 2026 | $8.9M | 0 | 0 | 0 min |
| Jun 2026 | $2.6M | 0 | 0 | 0 min |

| SOL (supply $7M) | AB: liquidated | AB: loss by end of path | AB: left unserved at trough | AB: queue p95 |
|---|---|---|---|---|
| FTX Nov 2022 | $4.9M | 0 | 0 | 0 min |
| Aug 2024 | $1.3M | 0 | 0 | 0 min |
| Oct 2025 | $0.78M | 0 | 0 | 0 min |
| Feb 2026 | $1.8M | 0 | 0 | 0 min |
| Jun 2026 | $0.54M | 0 | 0 | 0 min |

Scaling each book (same LTV distribution) to 2x, 4x, 8x, 16x and 32x today's size and replaying Oct 2025 shows no loss up to 32x today's book for either market; cbXRP at 32x has $0.30M underwater at the trough, SOL nothing. That is not because capacity holds. cbXRP's queue p95 is 75 min at 1x, 3 h at 2x and 24 h at 32x, with a peak queue of $887.3M at 32x; the loss stays zero because the book sits at low LTV and the Oct 2025 path stops short of the 88.7% bad-debt line for almost every position. The size rule in the previous paragraph is already breached at 2x.

## 7. What this does not capture

- Liquidator capital in a crash is unobserved. The only measurement is a day when it did not bind. It is the largest lever in the results and the least known input.
- The realized loss on March 2020 depends on the bounce. Holding the low for one day before the same recovery takes the 86% loss from $9.2M to $38.1M (2.4% of supply); the supply left unserved at the trough is a separate $158.4M; the only recoveries simulated are the historical bounce and that flat hold.
- Depth in a crash is scaled from today. We do not buy historical order books. Kaiko's Oct 10 2025 depth collapse, applied literally, contradicts the liquidations that happened that day.
- The March 2020 replay drops a 2026-sized book onto 2020 prices. BTC's market is far deeper now; it is also true that Oct 10 2025 produced the thinnest books Kaiko has ever measured.
- Borrower response is fit on three events with two parameters and assumes Coinbase's warning cadence stays as it is.
- Coinbase does not, on the public record, liquidate its own book, and the top liquidators trace to independent operators. The ABC column is a hypothetical commitment, not a description.
- Oracle behaviour is modeled as a one-bar lag on Coinbase's candle low. The replay of the Chainlink BTC/USD and ETH/USD paths on Base against Coinbase 5-minute candles (table below) puts the feed 0.07% to 0.16% from the Coinbase close at the median update and 1.26% to 6.50% from it at the worst update; the feed's low landed between 1.77% below and 0.55% above the Coinbase candle low, and reached it 25 s to 273 s after the candle, except ETH in Feb 2026, which never came within 0.5%. Median update interval 62 s to 182 s; longest gap 1232 s to 4600 s. The Oct 2025 BTC low 1.77% under Coinbase's is the multi-exchange feed printing a wick that Coinbase did not trade, which a lag on Coinbase's low cannot reproduce.

Chainlink on Base vs Coinbase 5-minute candles, from oracle_lag.json; deviation is |oracle - candle close| / close at each update; lag is candle low to the first oracle print within 0.5% of it.

| Window | Feed | Updates | Interval p50 / max | Deviation p50 / max | Oracle low vs candle low | Lag to the low |
|---|---|---|---|---|---|---|
| Oct 9-12 2025 | BTC | 1,395 | 122s / 1248s | 0.07% / 4.47% | -1.77% | 91s |
| Oct 9-12 2025 | ETH | 1,610 | 120s / 1232s | 0.12% / 6.50% | +0.16% | 25s |
| Feb 2-8 2026 | BTC | 4,912 | 62s / 1232s | 0.13% / 2.04% | +0.05% | 273s |
| Feb 2-8 2026 | ETH | 4,299 | 90s / 1232s | 0.16% / 2.33% | +0.55% | never within 0.5% |
| Jun 1-7 2026 | BTC | 3,410 | 120s / 1272s | 0.09% / 2.57% | +0.13% | 47s |
| Jun 1-7 2026 | ETH | 2,674 | 150s / 1292s | 0.11% / 3.81% | +0.20% | 171s |
| Jun 23-27 2026 | BTC | 1,583 | 150s / 4592s | 0.07% / 1.26% | +0.16% | 235s |
| Jun 23-27 2026 | ETH | 1,209 | 182s / 4600s | 0.08% / 1.75% | +0.03% | 141s |

## Changelog: what each revision changed in the recommendation

The cbBTC row is the one that moved. WETH has read 77% / 70% since the first draft; the alts have read 62.5% plus a size cap since the first draft, with the max draw cut to 47% in v2. Numbers below are as each version printed them.

| Date | Change to the model or data | cbBTC recommendation | March 2020 at 86% |
|---|---|---|---|
| 2026-09-15 (v1) | Today's book reshaped by haircut, full seizure, constant depth, borrower response fit on the three lived events (70% responsive, 2 h) | 80% / 70%, or keep 86% with a disclosed backstop | $64M bad debt (4.1% of supply) |
| 2026-09-15 | Bad-debt double count and stale queue flag fixed; depth-collapse sensitivity added | 80% / 70% and a pre-liquidation band | $24M (1.5%) at 30% surviving depth; $62-76M if depth collapses 90% |
| 2026-09-17 (Phase A) | Capacity margin below the bonus; Tier B liquidator capital capped at the observed daily maximum ($96.8M); calibration asserted within 25% of the three lived events | Backstop liquidator first; then 80% / 70% | $34-72M (2.2-4.6%) across the capital range |
| 2026-09-17 | Tier B cap moved to a rolling 24 h window and measured in seized units | Unchanged | $23-81M (1.5-5.1%) |
| 2026-09-18 (Phase E, v2) | Partial liquidations (repay to 74%, full close under $2.5k), vol-driven depth collapse, seed and liquidation-style sensitivities, origination cap from the p95 weekly drawdown | Cliff protocol first (full closes, backstop capital); then 80% / 66-70% | $140M (8.9%) under calm-day liquidator behaviour; $76M with full closes |
| 2026-09-18 (v3) | Full closes measured by debt repaid (80-94% of lived liquidations, not 28-50%); the model closes in full; beta off by default; exposure at the trough reported next to realized loss | Backstop liquidator first; then 80% / 66-70% | Loss by end of path $10M (0.7%); separately, $164M (10.4%) left unserved at the trough |
| 2026-09-19 (Phase G) | Ranges over hash seeds in the headline rows; held-at-the-low table; alt replays for cbXRP and SOL against Coinbase depth alone; book-size sweep to 32x; grid keyed by book date | Unchanged | Loss by end of path $9.2M (0.6%); separately, $158.4M (10.0%) left unserved at the trough; $38.1M loss if held a day at the low |

What the sequence shows: the first drafts overstated realized loss because they seized in full at a constant depth, then understated it once partial liquidations were taken from a miscounted sample. Once the lived events were measured by debt repaid, the headline stopped moving: realized loss on the worst path is single-digit millions and depends on the bounce; supply left unserved at the trough is about 10% and depends on liquidator capital, which the LLTV does not fix. That is why the recommendation leads with a backstop liquidator and puts the LLTV second.

## Sources

Morpho Blue API and contracts on Base; Coinbase Exchange public candles and L2 book; Chainlink BTC/USD and ETH/USD aggregators on Base; Morpho's Coinbase Dune dashboards; Kaiko research on Oct 2025 and March 2020 depth; Chaos Labs' Aave risk methodology; RiskDAO SmartLTV; Basel SCO60. Full citations in `research/`.
