# What haircut should Coinbase take on BTC and ETH collateral?

*Spine, 2026-09-18. Every number here is produced by a script in this repo from public data: the Morpho API, Base RPC, Coinbase Exchange, and Chainlink logs. Tables are printed by `spine/writeup_tables.py` from `data/backtest.json`, `data/calibration.json`, `data/summary.json`, `data/depth.json` and `data/caps.json`. The dashboard refreshes hourly.*

## The short version

Coinbase lends USDC against cbBTC and ETH on Morpho (Base) at an 86% liquidation LTV with a 4.38% liquidation bonus. The book is $1.41B of debt against $2.86B of cbBTC, 39,000 positions, 97.5% of it Coinbase Smart Wallets. It has been through three real stress events (Oct 2025, Feb 2026, Jun 2026), cleared $256M of liquidations in the four stress weeks alone, and taken zero bad debt.

That record is real and it is also not the test. The three lived events gave borrowers 23 hours to 4 days of warning before liquidation; March 2020 gave three. Replaying today's book through seven crash paths, with liquidators and borrowers behaving the way the lived events show they behave:

| Collateral | Today (LLTV / max draw) | Recommended | Why |
|---|---|---|---|
| cbBTC | 86% / 75% | **A cliff protocol first (full closes, backstop capital); then 80% / 66-70%** | March 2020 replay at 86%: $140M bad debt (8.9% of supply) if liquidators keep doing what they do on calm days, which is repay positions back to health and leave them open. Cutting the LLTV alone barely helps: $121M at 77%. Closing positions in full on a cliff halves it ($76M); a Coinbase backstop takes it to $23M; the two together at 80% LLTV, $10M. May 2021 and the five later paths are clean from 80% down once bots close in full |
| WETH | 86% / 75% | **77% / 70%** | ETH gaps more than the 4.38% bonus inside five minutes; at 86% three of seven paths leave bad debt even with unlimited depth. At 77% none do. cbETH already sits at 77% |
| cbXRP, SOL, cbDOGE, cbADA, cbLTC, JitoSOL | 62.5% / 55% | **62.5%**, max draw 47%, plus a per-asset book cap tied to Coinbase's own order-book depth | The 26-point buffer to the bad-debt line covers the worst observed 4-hour moves (-31% to -37%); the p95 weekly drawdown rule puts the cap at 46-48%. The constraint is disposal: none of these have a venue on Base |

Three things the replay makes clear. First, on a Black Thursday path the binding constraints are liquidator behaviour and liquidator capital, not the haircut: the same book loses 8.9% or 1.8% of supply at the same 86% LLTV depending on whether bots close positions or trim them, and on how much capital they can deploy in a day. Second, the LLTV only becomes an effective lever once bots close in full; under trim-and-leave, positions repaid to 74% come straight back on the next leg down. Third, the margin-call flow that protects borrowers in slow crashes does nothing on a cliff and slightly worsens it, which is why the recommendation includes draining the queue during the slide rather than at the cliff.

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

Latency is measured from the oracle update that pushed the position over 86% to the liquidation transaction. Bots are not the bottleneck. Every top-10 liquidator is a contract; the field is competitive (no address above a quarter of volume).

Two more facts about how they liquidate matter for what follows. Only 28-50% of liquidations closed the position; the rest repaid part of the debt and left the borrower open at a healthier LTV. And repaying a position from 87% back to 74% LTV costs 57% of its debt, because the seized collateral shrinks the denominator almost as fast as the repayment shrinks the numerator when the bonus is only 4.38%. A "partial" liquidation on Morpho is most of the position, and the remainder stays on the book.

Peak throughput on Feb 5 2026: $11.2M repaid in the busiest five minutes, $32.6M in the busiest hour, $96.8M in the day ($101M of collateral seized). Today's Coinbase BTC-USD bid book holds $35M within 4.38% of mid; on-chain cbBTC-to-USDC capacity at 4.38% slippage on Base is $3.5M across every Aerodrome and Uniswap pool. The busiest day is the only measurement we have of how much capital liquidators bring. It was not a binding day (everything that became liquidatable was cleared within seconds), so it is a floor on their capacity, not an estimate of it.

## 3. Borrowers respond, and it is not enough on a cliff

Take the exact cbBTC book on Feb 3 2026 ($1,075M debt, rebuilt from every transaction) and mark it at the Feb 6 trough ($60,001): $515M of debt crosses 86%. Only $151M was liquidated. Part of the gap is partial liquidations; the rest is borrowers topping up or repaying while Coinbase's margin warnings fired.

The model has three behavioural parameters, each pinned to something observed. Bots repay positions to 74% LTV and close outright only positions under $2,500, which reproduces the observed 38% full-close share (simulated 42%). A responsive share of borrowers repays to 74% once they have spent a reaction time inside the 80-86% warning zone; fitting that share and delay on the three cbBTC events gives 40% responsive with a four-hour reaction, reproducing all three within 21% (Feb 1.02x, Jun 1.14x, Oct 0.79x). Held-out WETH comes in at 2.08x and 1.25x. Without borrower response the same model overstates the three events by 1.3x, 1.9x and 1.1x; without partial liquidations it overstated them by 1.9-2.9x. Two parameters on three events deserves modest confidence and the share absorbs whatever else the model lacks; the ranking of effects is robust.

What the fit buys is time-dependence. Median time between entering the 80-86% zone and crossing 86%, for positions that ended up liquidated:

| Crash | Warning time for the median liquidated position |
|---|---|
| Oct 2025 | 3.6 days |
| Jun 2026 | 36 h |
| Aug 2024 | 26 h |
| FTX Nov 2022 | 25 h |
| Feb 2026 | 23 h |
| May 2021 | 12 h |
| **Mar 2020** | **3 h** |

Coinbase's borrower-warning flow works because crashes so far have been slow. On the March 2020 shape it changes little: with no borrower response at all the path costs $148M of bad debt, with the fitted response $140M, and even 90% of borrowers reacting within 15 minutes leaves $99M. On the slower May 2021 shape response matters ($47M with none, $31M fitted, $2M with 90% reacting fast). Borrowers can save a slow crash; only liquidators can save a fast one.

## 4. The backtest

Today's cbBTC book is dropped onto each historical path from its pre-crash peak at 5-minute resolution. Positions over LLTV enter a queue served largest-first. Liquidator capacity per step comes from measured depth read 1% inside the bonus, times a stress multiplier (DEX 0.5, CEX 0.3) that shrinks further with the trailing one-hour move (anchored on Kaiko's Oct 10 2025 measurement of top-of-book depth falling >90%), with 20% replenishment per step. Exchange-hedged liquidators are also limited by capital: a rolling 24-hour cap set by default to the most collateral the book has ever seen seized in a day ($101M, Feb 5 2026) and varied below. Bad debt is the shortfall on positions whose LTV passes 1/LIF (95.8% at 86% LLTV): realized when they are eventually liquidated underwater, or the trough shortfall of positions never liquidated. Three capacity scenarios:

- **A**: on-chain bots only (Base DEX depth).
- **AB**: plus liquidators who seize cbBTC and sell BTC on Coinbase and Kraken. This matches observed behaviour.
- **ABC**: plus Coinbase itself redeeming cbBTC 1:1, effectively unlimited depth and capital at the exchange price. Whether Coinbase runs such a liquidator is not public.

cbBTC at today's terms (86% / 75%), fitted behaviour:

| Path | Worst 4h / 24h | AB: liquidated | AB: bad debt | AB: queue p50 / p95 | ABC: bad debt |
|---|---|---|---|---|---|
| Mar 2020 | -35% / -50% | $833M | **$140M (8.9%)** | 3.2 days / 3.8 days | $23M (1.5%) |
| May 2021 | -26% / -32% | $566M | **$31M (1.9%)** | 15 h / 6.2 days | $1.0M |
| FTX Nov 2022 | -15% / -19% | $135M | 0 | 0 / 14 h | 0 |
| Aug 2024 | -11% / -20% | $151M | 0 | 0 / 19 h | 0 |
| Oct 2025 | -10% / -13% | $28M | 0 | 0 / 0 | 0 |
| Feb 2026 | -9% / -18% | $180M | 0 | 0 / 4.9 days | 0 |
| Jun 2026 | -7% / -9% | $58M | 0 | 0 / 0 | 0 |

Percentages are of the $1.57B USDC supplied to the market. Bad debt on Morpho is socialized to suppliers, which includes depositors in the Coinbase USDC lending product, not Coinbase's balance sheet.

The table that decides the recommendation is the one that varies what liquidators do and how much capital they have. March 2020 and May 2021, scenario AB:

| Path, LLTV | Trim to 74%, capital as observed | Full close, capital as observed | Trim to 74%, unlimited capital | Full close, unlimited capital |
|---|---|---|---|---|
| Mar 2020, 86% | $140M (8.9%) | $76M (4.8%) | $96M (6.1%) | $28M (1.8%) |
| Mar 2020, 80% | $123M (7.8%) | $49M (3.1%) | $60M (3.8%) | $10M (0.7%) |
| Mar 2020, 77% | $121M (7.7%) | $35M (2.3%) | $44M (2.8%) | $4M (0.3%) |
| May 2021, 86% | $31M (1.9%) | $10M (0.6%) | $22M (1.4%) | $8M (0.5%) |
| May 2021, 80% | $16M (1.0%) | $3M (0.2%) | $7M (0.4%) | $1M (0.1%) |
| May 2021, 77% | $11M (0.7%) | $0.6M | $2.5M (0.2%) | 0 |

Read across the first row: the same book at the same LLTV loses between 1.8% and 8.9% of supply depending on two things Coinbase does not currently control and nobody publishes. Read down the first column: under calm-day liquidator behaviour, cutting the LLTV from 86% to 77% recovers almost nothing, because a position trimmed to 74% is back in the queue after the next 14% leg and the cliff has several. Read down the second column: once bots close in full, the LLTV works again and each cut buys about a point of supply. The liquidator capital multiples in between (3x observed: $127M trimming, 10x: $96M) say capital alone is the weaker of the two levers.

The exchange-depth multiplier and the hash seed that decides which wallets are responsive move results by 1-3% and are not shown. Bad-debt LTV per LLTV: 86% → 95.8%, 80% → 94.0%, 77% → 93.1%; a lower LLTV also raises Morpho's liquidation bonus, which is why the full-close column improves faster than the trim column.

WETH at 86% / 75%: March 2020 $0.5-1.4M, May 2021 up to $0.4M, Aug 2024 $0.2M of bad debt across scenarios, and more with unlimited depth than without (about 1.5% of that market's $92M supply at worst), because ETH gaps more than 4.38% inside five minutes and a backstop that liquidates everything instantly realizes the gap. At 80%, under $0.6M on March 2020 only; at 77%, every path is clean under every scenario.

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

RiskDAO's SmartLTV formula (LTV = exp(−c·σ/√(l/d)) − β, with l the liquidity inside the bonus and d the borrow) is a useful cross-check because it fails loudly: for cbBTC it returns 4.8% at its mildest calibration and negative at the others. With $68M of measured bids inside the 4.38% bonus against a $1.42B book, the formula is saying the book is twenty times too large for the liquidity at the bonus, not that the LLTV is wrong. That is the same finding as section 4 from a different direction.

## 6. The argument, in one line per asset

The rule: **1 − LLTV must cover the worst move over the time it takes to clear the queue, plus the liquidation bonus, plus one oracle interval.** Basel's SCO60.29 says the same thing in regulator language: assess the liquidation period and downturn liquidity depth before recognizing crypto collateral.

**cbBTC.** On a March 2020 path the queue takes three days to clear at the median with the capital liquidators brought on Feb 5 2026, and BTC fell 58% peak to trough over that week. No LLTV covers that on its own, and under the way bots actually liquidate, no LLTV in the grid gets the worst-path loss below 7.7% of supply. What does work, in order of effect: a cliff protocol, meaning liquidators that close positions in full when the queue exceeds capacity (halves the loss at any LLTV, and is a liquidator policy, not a parameter change); a backstop liquidator that can redeem cbBTC and sell BTC on Coinbase's own book (the ABC column: $23M at 86%, zero at 77%), which belongs to Coinbase alone and should be published because lenders are pricing it whether it exists or not; and then the LLTV, where 80% with full closes costs 3.1% of supply on the worst path and is clean everywhere else. The origination cap follows from section 5: 66% at 80% LLTV on the full history, 70% if only the post-2022 regime counts. Comparators: Aave sets cbBTC on Base at a 78% liquidation threshold; Ledn liquidates at 80%; Unchained at 83% with a 24-hour cure period.

**Pre-liquidation, whichever LLTV is chosen.** Morpho supports pre-liquidation contracts: a band (say 80-86% LTV) where positions can be partially closed at a small bonus (1-2%) before the hard line. On a slow slide it drains the queue while capacity is idle. It costs borrowers less than a 4.38% liquidation and it is the on-chain form of the margin call Coinbase already sends.

**WETH.** 77%. Same as Coinbase already uses for cbETH, and the only setting in the grid that survives all seven paths under every scenario. The cost is small: the market is $83M. Cap 59-62% by the p95 rule.

**Alts at 62.5%.** The volatility buffer is adequate: the bad-debt line is a further 29.6% below the liquidation line, and the worst observed 4-hour moves are -31% (XRP, Mar 2020), -35% (XRP, Oct 2025), -37% (DOGE, Oct 2025), -34% (SOL, FTX). The max draw should come down from 55% to the p95 cap of 46-48%. What is missing is a size rule. There is no on-chain venue for cbXRP, cbDOGE, cbADA or cbLTC on Base; every seized unit must be redeemed through Coinbase and sold on Coinbase's book, which holds $8-10M of XRP or SOL bids within 10% of mid against a 12.7% bonus. A per-asset cap of the form "debt that would be liquidatable at -30% must not exceed one hour of Coinbase's own depth" keeps these markets in the regime where 62.5% is safe. cbXRP at $48M is the one to watch.

## 7. What this does not capture

- Whether bots trim or close on a cliff day is the largest single assumption and it is unobserved; the lived events were calm enough that trimming was rational. Both columns are shown.
- Liquidator capital in a crash is unobserved. The only measurement is a day when it did not bind.
- Depth in a crash is scaled from today with one anchor point (Oct 10 2025). We do not buy historical order books. It turns out to matter less than the two points above.
- The March 2020 replay drops a 2026-sized book onto 2020 prices. BTC's market is far deeper now; it is also true that Oct 10 2025 produced the thinnest books Kaiko has ever measured.
- Borrower response is fit on three events with two parameters and assumes Coinbase's warning cadence stays as it is.
- Whether Coinbase liquidates its own book is unverified. It is the ABC column.
- Oracle behaviour is modeled as a one-bar lag on Coinbase's candle low. The Chainlink path on Base tracked the exchange low within 0.1% on the lived events.

## Sources

Morpho Blue API and contracts on Base; Coinbase Exchange public candles and L2 book; Chainlink BTC/USD and ETH/USD aggregators on Base; Morpho's Coinbase Dune dashboards; Kaiko research on Oct 2025 and March 2020 depth; Chaos Labs' Aave risk methodology; RiskDAO SmartLTV; Basel SCO60. Full citations in `research/`.
