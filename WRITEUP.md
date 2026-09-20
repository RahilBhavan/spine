# What haircut should Coinbase take on BTC and ETH collateral?

*Spine, 2026-09-19. Every number here is produced by a script in this repo from public data: the Morpho API, Base RPC, Coinbase Exchange, and Chainlink logs. Tables are printed by `spine/writeup_tables.py` and `spine/caps.py` from `data/backtest.json`, `data/calibration.json`, `data/summary.json`, `data/depth.json` and `data/caps.json`. The dashboard refreshes hourly.*

## The short version

Coinbase lends USDC against cbBTC and ETH on Morpho (Base) at an 86% liquidation LTV with a 4.38% liquidation bonus. The book is $1.41B of debt against $2.86B of cbBTC, 39,000 positions, 97.5% of it Coinbase Smart Wallets. It has been through three real stress events (Oct 2025, Feb 2026, Jun 2026), cleared $256M of liquidations in the four stress weeks alone, and taken zero bad debt.

That record is real and it is also not the test. The lived events gave borrowers hours to days of warning before liquidation; March 2020 gave 25 minutes. Replaying today's book through seven crash paths, with liquidators and borrowers behaving the way the lived events show they behave, two numbers matter for each path: the loss that is realized by the end of the path, and the exposure at the lowest print, meaning how much of the book is underwater with no liquidator able to act. The first is what lenders lost; the second is what they were exposed to, and it becomes the first if the price does not bounce.

| Collateral | Today (LLTV / max draw) | Recommended | Why |
|---|---|---|---|
| cbBTC | 86% / 75% | **A committed backstop liquidator first; then 80% / 66-70%** | March 2020 replay at 86%: $9.2M realized (0.6% of supply) but $158.4M underwater and unserved at the trough (10.0%). Cutting the LLTV alone does little to the second number (77%: 8.4%), because liquidator capital, not the haircut, is what binds. Tripling liquidator capital takes it to 6.2%; a Coinbase backstop takes it to 0.8% with nothing left unserved. At 80% every other path is clean |
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

We model this as a responsive share of borrowers who repay to 74% LTV once they have spent a reaction time inside the 80-86% warning zone. Fitting the share and the delay on the three cbBTC events gives 70% responsive with a two-hour reaction, reproducing all three within 15% (Feb 0.99x, Jun 0.85x, Oct 0.95x). Held-out WETH comes in at 1.58x and 0.85x. Without borrower response the same model overstates the three events by 2.0x, 2.9x and 1.7x. The fit is a plateau (60-70% responsive, one to two hours all fit about equally), so read those as ranges: on March 2020 the four cells give loss / exposure of $9.1M / $150.2M (60%, 1 h), $9.1M / $159.5M (60%, 2 h), $9.0M / $147.3M (70%, 1 h) and $9.2M / $158.4M (70%, 2 h). Two parameters on three events deserves modest confidence and the share absorbs whatever else the model lacks. The ranking of effects is robust.

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

| Path | Worst 4h / 24h | AB: liquidated | AB: loss by end of path | AB: exposure at trough | AB: queue p50 / p95 | ABC: loss / exposure |
|---|---|---|---|---|---|---|
| Mar 2020 | -35% / -50% | $618.3M | **$9.2M (0.6%)** ($8.3M-$9.2M) | **$158.4M (10.0%)** | 2.0 days / 3.3 days | $13.1M (0.8%) / $13.1M (0.8%) |
| May 2021 | -26% / -32% | $356.5M | $0.28M (0.0%) ($0.11M-$0.45M) | $17.1M (1.1%) | 11 h / 4.1 days | $0.73M (0.0%) / $0.73M (0.0%) |
| FTX Nov 2022 | -15% / -19% | $64.6M | 0 | 0 | 0 min / 10 min | 0 / 0 |
| Aug 2024 | -11% / -20% | $81.5M | 0 | 0 | 0 min / 6 h | 0 / 0 |
| Oct 2025 | -10% / -13% | $18.0M | 0 | 0 | 0 min / 0 min | 0 / 0 |
| Feb 2026 | -9% / -18% | $94.6M | 0 | 0 | 0 min / 5 min | 0 / 0 |
| Jun 2026 | -7% / -9% | $25.7M | 0 | 0 | 0 min / 0 min | 0 / 0 |

Percentages are of the $1.58B USDC supplied to the market; the range in brackets is the loss over ten reshuffles of which wallets are responsive. Bad debt on Morpho is socialized to suppliers, which includes depositors in the Coinbase USDC lending product, not Coinbase's balance sheet.

The March 2020 row is the whole argument. By the end of the path lenders lose 0.6% of supply, because BTC bounced from $3,858 to over $5,000 within hours and the queue was served above water on the way back up. At the low, 10.0% of supply sat underwater with a queue of two days. Under the backstop scenario the queue is served at the low itself, which realizes the oracle-jump shortfall ($13.1M) and leaves nothing exposed. A lender does not get to choose which of those numbers to be judged on; the bounce did.

What moves the trough exposure. Scenario AB, March 2020, loss / exposure:

| LLTV | Capital as observed ($101.1M/day) | 3x | 10x | Depth-limited only |
|---|---|---|---|---|
| 86% | $9.2M (0.6%) / $158.4M (10.0%) | $2.2M (0.1%) / $97.7M (6.2%) | $2.1M (0.1%) / $75.2M (4.7%) | $2.1M (0.1%) / $75.2M (4.7%) |
| 80% | $4.0M (0.3%) / $143.0M (9.0%) | $0.70M (0.0%) / $91.8M (5.8%) | $1.2M (0.1%) / $54.1M (3.4%) | $1.2M (0.1%) / $54.1M (3.4%) |
| 77% | $2.4M (0.2%) / $133.5M (8.4%) | $1.1M (0.1%) / $88.7M (5.6%) | $1.5M (0.1%) / $38.0M (2.4%) | $1.5M (0.1%) / $38.0M (2.4%) |

Read down a column: the LLTV buys about a point of supply from 86% to 80% and half a point from 80% to 77%. Read across a row: tripling liquidator capital buys three to four points, and unlimited capital five to six. At 70% and 62.5% LLTV (with a 60% max draw) the exposure falls to $25-28M and the realized loss to rounding dust, but that is a different product. On May 2021 the exposure is $17.1M (1.1%) at 86% and under $2M from 80% down, at any capital level.

The gap between loss and exposure is the bounce. To see what a slower recovery costs, the same paths are replayed with the trough low held for an hour and for a day before the historical bounce resumes:

| Path | LLTV | Loss, no hold | Loss, held 1 h | Loss, held 1 day | Exposure at trough |
|---|---|---|---|---|---|
| Mar 2020 | 86% | $9.2M (0.6%) | $9.7M (0.6%) | $38.1M (2.4%) | $158.4M (10.0%) |
| Mar 2020 | 80% | $4.0M (0.3%) | $4.6M (0.3%) | $29.7M (1.9%) | $143.0M (9.0%) |
| Mar 2020 | 77% | $2.4M (0.2%) | $2.6M (0.2%) | $26.0M (1.6%) | $133.5M (8.4%) |
| May 2021 | 86% | $0.28M (0.0%) | $0.59M (0.0%) | $5.3M (0.3%) | $17.1M (1.1%) |
| May 2021 | 80% | 0 | 0 | $0.20M (0.0%) | $1.1M (0.1%) |
| May 2021 | 77% | 0 | 0 | $0.00M (0.0%) | $0.20M (0.0%) |

An hour at the low changes little; a day at the low quadruples the March 2020 loss at 86% and shrinks what the LLTV buys in relative terms (cutting 86% to 77% removes three-quarters of the loss with no hold, a third after a day at the low), because the queue is then served at the low and liquidator capital decides how much of the exposure is realized.

Whether bots trim positions instead of closing them (trim to 74%, which on Morpho means repaying about two-thirds of the debt), the exchange-depth multiplier, a volatility-driven depth collapse, and the hash seed that decides which wallets are responsive each move these results by a few percent and are in `data/backtest.json`. The depth-collapse term was anchored on Kaiko's Oct 10 2025 measurement and turned off by default because it under-predicts the liquidations that actually happened that day by 40%.

WETH at 86% / 75%: March 2020 $0.93-1.1M, May 2021 $0.25M, Aug 2024 $0.15M of loss across scenarios (about 1.1% of that market's $94M supply at worst), because ETH gaps more than 4.38% inside five minutes and a backstop that liquidates everything instantly realizes the gap. At 80%, $0.13-0.21M on March 2020 and $0.02M on May 2021; at 77%, every path is clean under every scenario.

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

**cbBTC.** On a March 2020 path the queue takes two days to clear at the median with the capital liquidators brought on Feb 5 2026, and BTC fell 58% peak to trough over that week. No LLTV covers that: 77% still leaves 8.4% of supply underwater at the low. What does: a backstop liquidator that can redeem cbBTC and sell BTC on Coinbase's own book (the ABC column: 0.8% realized at 86%, zero at 77%, nothing left unserved). Only Coinbase can be that liquidator, nothing public says it is, and USDC suppliers are lending as if the answer were known; then the LLTV, where 80% costs 0.3% realized and 9.0% exposed on the worst path and is clean everywhere else. The origination cap follows from section 5: 66% at 80% LLTV on the full history, 70% if only the post-2022 regime counts. Comparators: Aave sets cbBTC on Base at a 78% liquidation threshold; Ledn liquidates at 80%; Unchained at 83% with a 24-hour cure period.

**Pre-liquidation, whichever LLTV is chosen.** Morpho supports pre-liquidation contracts: a band (say 80-86% LTV) where positions can be partially closed at a small bonus (1-2%) before the hard line. On a slow slide it drains the queue while capacity is idle. It costs borrowers less than a 4.38% liquidation and it is the on-chain form of the margin call Coinbase already sends.

**WETH.** 77%. Same as Coinbase already uses for cbETH, and the only setting in the grid that survives all seven paths under every scenario. The cost is small: the market is $83M. Cap 59-62% by the p95 rule.

**Alts at 62.5%.** The volatility buffer is adequate: the bad-debt line is a further 29.6% below the liquidation line, and the worst observed 4-hour moves are -31% (XRP, Mar 2020), -35% (XRP, Oct 2025), -37% (DOGE, Oct 2025), -34% (SOL, FTX). The max draw should come down from 55% to the p95 cap of 46-48%. What is missing is a size rule. There is no on-chain venue for cbXRP, cbDOGE, cbADA or cbLTC on Base; every seized unit must be redeemed through Coinbase and sold on Coinbase's book, which holds $8-10M of XRP or SOL bids within 10% of mid against a 12.7% bonus. The per-asset cap: debt that would be liquidatable at -30% must not exceed one hour of Coinbase's own depth (one hour of Tier B collateral capacity at 62.5%, converted to debt at the bonus). Today's distribution: cbXRP has $10.7M liquidatable at -30% against a one-hour cap of $20.9M (1.9x headroom); SOL $1.4M against $29.0M (20.2x). Drawn to the 55% max draw, the whole book is liquidatable at -30% (55/0.70 = 78.6% > 62.5%), so the cap is $20.9M of debt for cbXRP and $29.0M for SOL; today's books are $48.7M and $5.5M. cbXRP is already past it and is the one to watch. Replaying the two alt books with data (cbXRP, SOL) at 62.5% / 55% against Coinbase depth alone:

| cbXRP (supply $54M) | AB: liquidated | AB: loss by end of path | AB: exposure at trough | AB: queue p95 |
|---|---|---|---|---|
| Mar 2020 | $32.3M | 0 | 0 | 11 h |
| Aug 2024 | $7.8M | 0 | 0 | 50 min |
| Oct 2025 | $9.8M | 0 | 0 | 75 min |
| Feb 2026 | $8.9M | 0 | 0 | 0 min |
| Jun 2026 | $2.6M | 0 | 0 | 0 min |

| SOL (supply $7M) | AB: liquidated | AB: loss by end of path | AB: exposure at trough | AB: queue p95 |
|---|---|---|---|---|
| FTX Nov 2022 | $4.9M | 0 | 0 | 0 min |
| Aug 2024 | $1.3M | 0 | 0 | 0 min |
| Oct 2025 | $0.78M | 0 | 0 | 0 min |
| Feb 2026 | $1.8M | 0 | 0 | 0 min |
| Jun 2026 | $0.54M | 0 | 0 | 0 min |

Scaling each book (same LTV distribution) to 2x, 4x, 8x, 16x and 32x today's size and replaying Oct 2025 shows no loss up to 32x today's book for either market; cbXRP at 32x has $0.30M underwater at the trough, SOL nothing. That is not because capacity holds. cbXRP's queue p95 is 75 min at 1x, 3 h at 2x and 24 h at 32x, with a peak queue of $887.3M at 32x; the loss stays zero because the book sits at low LTV and the Oct 2025 path stops short of the 88.7% bad-debt line for almost every position. The size rule in the previous paragraph is already breached at 2x.

## 7. What this does not capture

- Liquidator capital in a crash is unobserved. The only measurement is a day when it did not bind. It is the largest lever in the results and the least known input.
- The realized loss on March 2020 depends on the bounce. Holding the low for one day before the same recovery takes the 86% loss from $9.2M to $38.1M (2.4% of supply) against $158.4M exposed; the only recoveries simulated are the historical bounce and that flat hold.
- Depth in a crash is scaled from today. We do not buy historical order books. Kaiko's Oct 10 2025 depth collapse, applied literally, contradicts the liquidations that happened that day.
- The March 2020 replay drops a 2026-sized book onto 2020 prices. BTC's market is far deeper now; it is also true that Oct 10 2025 produced the thinnest books Kaiko has ever measured.
- Borrower response is fit on three events with two parameters and assumes Coinbase's warning cadence stays as it is.
- Coinbase does not, on the public record, liquidate its own book, and the top liquidators trace to independent operators. The ABC column is a hypothetical commitment, not a description.
- Oracle behaviour is modeled as a one-bar lag on Coinbase's candle low. The Chainlink path on Base tracked the exchange low within 0.1% on the lived events.

## Changelog: what each revision changed in the recommendation

The cbBTC row is the one that moved. WETH has read 77% / 70% since the first draft; the alts have read 62.5% plus a size cap since the first draft, with the max draw cut to 47% in v2. Numbers below are as each version printed them.

| Date | Change to the model or data | cbBTC recommendation | March 2020 at 86% |
|---|---|---|---|
| 2026-09-15 (v1) | Today's book reshaped by haircut, full seizure, constant depth, borrower response fit on the three lived events (70% responsive, 2 h) | 80% / 70%, or keep 86% with a disclosed backstop | $64M bad debt (4.1% of supply) |
| 2026-09-15 | Bad-debt double count and stale queue flag fixed; depth-collapse sensitivity added | 80% / 70% and a pre-liquidation band | $24M (1.5%) at 30% surviving depth; $62-76M if depth collapses 90% |
| 2026-09-17 (Phase A) | Capacity margin below the bonus; Tier B liquidator capital capped at the observed daily maximum ($96.8M); calibration asserted within 25% of the three lived events | Backstop liquidator first; then 80% / 70% | $34-72M (2.2-4.6%) across the capital range |
| 2026-09-17 | Tier B cap moved to a rolling 24 h window and measured in seized units | Unchanged | $23-81M (1.5-5.1%) |
| 2026-09-18 (Phase E, v2) | Partial liquidations (repay to 74%, full close under $2.5k), vol-driven depth collapse, seed and liquidation-style sensitivities, origination cap from the p95 weekly drawdown | Cliff protocol first (full closes, backstop capital); then 80% / 66-70% | $140M (8.9%) under calm-day liquidator behaviour; $76M with full closes |
| 2026-09-18 (v3) | Full closes measured by debt repaid (80-94% of lived liquidations, not 28-50%); the model closes in full; beta off by default; exposure at the trough reported next to realized loss | Backstop liquidator first; then 80% / 66-70% | $10M realized (0.7%), $164M exposed at the trough (10.4%) |
| 2026-09-19 (Phase G) | Ranges over hash seeds in the headline rows; held-at-the-low table; alt replays for cbXRP and SOL against Coinbase depth alone; book-size sweep to 32x; grid keyed by book date | Unchanged | $9.2M realized (0.6%), $158.4M exposed (10.0%); $38.1M realized if held a day at the low |

What the sequence shows: the first drafts overstated realized loss because they seized in full at a constant depth, then understated it once partial liquidations were taken from a miscounted sample. Once the lived events were measured by debt repaid, the headline stopped moving: realized loss on the worst path is single-digit millions and depends on the bounce; exposure at the trough is about 10% of supply and depends on liquidator capital, which the LLTV does not fix. That is why the recommendation leads with a backstop liquidator and puts the LLTV second.

## Sources

Morpho Blue API and contracts on Base; Coinbase Exchange public candles and L2 book; Chainlink BTC/USD and ETH/USD aggregators on Base; Morpho's Coinbase Dune dashboards; Kaiko research on Oct 2025 and March 2020 depth; Chaos Labs' Aave risk methodology; RiskDAO SmartLTV; Basel SCO60. Full citations in `research/`.
