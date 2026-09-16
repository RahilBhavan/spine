# What haircut should Coinbase take on BTC and ETH collateral?

*Spine, 2026-09-15. Every number here is produced by a script in this repo from public data: the Morpho API, Base RPC, Coinbase Exchange, and Chainlink logs. The dashboard refreshes hourly. Backtest and calibration outputs are in `data/backtest.json` and `data/calibration.json`.*

## The short version

Coinbase lends USDC against cbBTC and ETH on Morpho (Base) at an 86% liquidation LTV with a 4.38% liquidation bonus. The book is $1.41B of debt against $2.86B of cbBTC, 39,000 positions, 97.5% of it Coinbase Smart Wallets. It has been through three real stress events (Oct 2025, Feb 2026, Jun 2026), cleared $256M of liquidations in the four stress weeks alone, and taken zero bad debt.

That record is real and it is also not the test. The three lived events gave borrowers 22 to 86 hours of warning before liquidation; March 2020 gave 20 minutes. Replaying today's book through the seven crash paths:

| Collateral | Today (LLTV / max draw) | Recommended | Why |
|---|---|---|---|
| cbBTC | 86% / 75% | **80% / 70%**, and a pre-liquidation band at 80-86% | March 2020 replay at 86%: $24M bad debt (1.5% of supply) if 30% of today's exchange depth survives, $62-76M (4-5%) if depth collapses 90% as it did on Oct 10 2025. At 80%: $7M (0.4%). At 77%: $3M. Every other path is clean at every setting |
| WETH | 86% / 75% | **77% / 70%** | ETH gaps more than the 4.38% bonus inside five minutes; at 86% three of seven paths leave bad debt even with unlimited depth. At 77% none do. cbETH already sits at 77% |
| cbXRP, SOL, cbDOGE, cbADA, cbLTC, JitoSOL | 62.5% / 55% | **62.5%**, plus a per-asset book cap tied to Coinbase's own order-book depth | The 26-point buffer to the bad-debt line covers the worst observed 4-hour moves (-31% to -37%). The constraint is disposal: none of these have a venue on Base, so every liquidation routes through Coinbase redemption |

Two things the replay makes clear. First, the lever is the liquidation LTV, not the origination cap: on Morpho a lower LLTV also raises the liquidation bonus, so it widens the gap to the bad-debt line twice. At 86% a liquidated position is underwater after a further 10.2% drop; at 80% after 14.5%; at 77% after 16.5%. March 2020's worst four hours were -35%. Second, the margin-call flow that protects borrowers in slow crashes makes cliff-shaped crashes worse for lenders, which is why the recommendation includes draining the queue during the slide rather than at the cliff.

## 1. What the book looks like

- cbBTC/USDC 86%: $1.413B borrowed, $2.860B collateral, utilization 90%, borrow APY 4.8%. Book LTV 49%; most debt sits between 40% and 65% LTV. Largest position $5.2M.
- Eight more Coinbase markets (WETH 86%, cbETH 77%, six alts at 62.5%) add $154M. WETH is the only one that matters for size ($83M).
- A -10% instantaneous move puts $30M of debt over the 86% line; -20%, $112M; -30%, $336M. Morpho's own Dune dashboard shows the same curve and puts $1.1B of collateral at risk at -50%.
- Realized bad debt across all nine markets since inception: $0.07, rounding dust.

## 2. Who liquidates it, and how fast

From every liquidation in the three lived events, valued at the Chainlink price in the liquidation block:

| Window | cbBTC liquidations | Repaid | Seized | Bonus (p50) | Latency p50 / p90 | Within 60s | Liquidators | Top share |
|---|---|---|---|---|---|---|---|---|
| Oct 9-12 2025 | 410 | $17.6M | $18.4M | 4.38% | 4s / 70s | 90% | 21 | 23% |
| Feb 2-8 2026 | 4,116 | $150.8M | $157.4M | 4.38% | 2s / 88s | 87% | 46 | 16% |
| Jun 1-7 2026 | 3,308 | $72.1M | $75.3M | 4.38% | 0s / 6s | 97% | 110 | 11% |
| Jun 23-27 2026 | 394 | $15.4M | $16.0M | 4.38% | 0s / 6s | 98% | 43 | 23% |

Latency is measured from the oracle update that pushed the position over 86% to the liquidation transaction. Bots are not the bottleneck. Every top-10 liquidator is a contract; the field is competitive (no address above a quarter of volume). Most liquidations are partial (28-51% full), which is what you expect from bots sizing to available depth.

Peak throughput on Feb 5 2026: $11.2M repaid in the busiest five minutes, $32.6M in the busiest hour. Today's Coinbase BTC-USD bid book holds $33M within 4.38% of mid; on-chain cbBTC-to-USDC capacity at 4.38% slippage on Base is $3.5M across every Aerodrome and Uniswap pool. The busiest hour of the book's life consumed roughly one full order book of depth. That is the number the stress tests have to respect.

## 3. Borrowers matter more than liquidators

The largest correction to a naive model came from the data. Take the exact cbBTC book on Feb 3 2026 ($1,075M debt, rebuilt from every transaction) and mark it at the Feb 6 trough ($60,001): $515M of debt crosses 86%. Only $151M was liquidated. Borrowers cured about 70% of at-risk debt by topping up or repaying while Coinbase's margin warnings fired.

We model this as a responsive share of borrowers who repay to 74% LTV once they have spent a reaction time inside the warning zone (80-86% LTV). Fitting the share and the delay on the three cbBTC events gives 70% responsive and a two-hour reaction, and reproduces all three within 15% (Feb 1.03x, Jun 0.85x, Oct 0.95x). Held-out WETH comes in at 1.58x and 0.85x. Two parameters on three events deserves modest confidence, and the share absorbs whatever else the model lacks (depth assumptions, partial fills). The qualitative point is robust: without it, every replay of a lived event overstates liquidations two to three times.

What the fit buys is time-dependence. Median warning time between entering the 80-86% zone and crossing 86%:

| Crash | Warning time for the median liquidated position |
|---|---|
| Oct 2025 | 86 hours |
| Jun 2026 | 41 hours |
| Feb 2026 | 22 hours |
| Aug 2024 | 8 hours |
| May 2021 | 8 hours |
| **Mar 2020** | **20 minutes** |

Coinbase's borrower-warning flow works because crashes so far have been slow. It cannot work on a Black Thursday shape.

The uncomfortable result: on cliff-shaped paths, borrower response raises lender losses. March 2020 replay at today's terms, observed liquidator capacity:

| Borrowers | Liquidated | Bad debt |
|---|---|---|
| None respond | $1,275M | $7.9M |
| 70% respond within 2 h (fitted) | $1,042M | $23.7M |
| 70% respond within 15 min | $752M | $47.4M |
| 90% respond within 15 min | $605M | $57.4M |

During the multi-day slide before March 12, responsive borrowers top up to 74% instead of being liquidated at 86% while liquidator capacity sits idle. On the 50% day they all cross at once into a $1B queue, and the ones served hours late realize shortfall. Faster and broader response makes it worse. On the slower May 2021 shape, a fast response helps ($1.0M vs $12.1M at two hours). The margin call protects borrowers and concentrates lender risk onto the cliff.

## 4. The backtest

Today's cbBTC book is dropped onto each historical path from its pre-crash peak at 5-minute resolution. Positions over LLTV enter a queue served largest-first. Liquidator capacity per step comes from measured depth times a stress multiplier (DEX 0.5, CEX 0.3) with 20% replenishment per step. Bad debt is the shortfall on positions whose LTV passes 1/LIF (95.8% at 86% LLTV): realized when they are eventually liquidated underwater, or the trough shortfall of positions never liquidated. Three capacity scenarios:

- **A**: on-chain bots only (Base DEX depth).
- **AB**: plus liquidators who seize cbBTC and sell BTC on Coinbase and Kraken. This matches observed behaviour.
- **ABC**: plus Coinbase itself redeeming cbBTC 1:1, effectively unlimited depth at the exchange price. Whether Coinbase runs such a liquidator is not public.

cbBTC at today's terms (86% / 75%), fitted borrower response:

| Path | Worst 4h / 24h | AB: liquidated | AB: bad debt | AB: queue p50 / p95 | ABC: bad debt |
|---|---|---|---|---|---|
| Mar 2020 | -35% / -50% | $1,042M | **$23.7M (1.5%)** | 12 h / 3.5 days | $19.6M (1.2%) |
| May 2021 | -26% / -32% | $449M | **$12.1M (0.8%)** | 35 min / 4 days | $0.8M |
| FTX Nov 2022 | -15% / -19% | $99M | 0 | 0 / 10 min | 0 |
| Aug 2024 | -11% / -20% | $132M | 0 | 0 / 6 h | 0 |
| Oct 2025 | -10% / -13% | $35M | 0 | 0 / 5 min | 0 |
| Feb 2026 | -9% / -18% | $159M | 0 | 0 / 0 | 0 |
| Jun 2026 | -7% / -9% | $44M | 0 | 0 / 0 | 0 |

Percentages are of the $1.57B USDC supplied to the market. Bad debt on Morpho is socialized to suppliers, which includes depositors in the Coinbase USDC lending product, not Coinbase's balance sheet.

Bad debt across the LLTV grid, cbBTC, fitted response. Max draw 75% (60% for the two lowest rows, where 75% would exceed the LLTV):

| LLTV | Bad-debt LTV (1/LIF) | AB: Mar 2020 | AB: May 2021 | ABC: Mar 2020 | ABC: May 2021 | Other five paths |
|---|---|---|---|---|---|---|
| 86% | 95.8% | $23.7M | $12.1M | $19.6M | $0.8M | 0 |
| 80% | 93.6% | $6.6M | $0.04M | $4.0M | 0 | 0 |
| 77% | 92.2% | $2.9M | 0 | 0 | 0 | 0 |
| 70% | 89.6% | $0.2M | 0 | 0 | 0 | 0 |
| 62.5% | 88.7% | 0 | 0 | 0 | 0 | 0 |

With a Coinbase backstop (ABC), 77% clears every path, and 86% still leaves $20M on March 2020 that no amount of depth removes: it is the gap between two 5-minute oracle updates exceeding the bonus.

The sensitivity that matters is exchange depth in the crash. At 86% on March 2020 under AB: if 10% of today's Coinbase and Kraken depth survives, bad debt is $62-76M (4-5% of supply); at 30%, $24M; at 100%, $8M. Kaiko measured top-of-book BTC depth falling more than 90% intraday on Oct 10 2025. The 30% default is not conservative. DEX depth and oracle lag move results by 10-20% within a row.

WETH at 86% / 75%: March 2020 $0.9-1.3M, May 2021 $0.3M, Aug 2024 $0.3M of bad debt under every scenario, and slightly more with unlimited depth than without (about 1% of that market's supply at worst). WETH's problem is not depth (Base has $26M+ of WETH-to-USDC capacity at 4.38%), it is that ETH gaps more than 4.38% inside five minutes. At 80%, $0.1M; at 77%, every path is clean.

## 5. The argument, in one line per asset

The rule: **1 - LLTV must cover the worst move over the time it takes to clear the queue, plus the liquidation bonus, plus one oracle interval.** Basel's SCO60.29 says the same thing in regulator language: assess the liquidation period and downturn liquidity depth before recognizing crypto collateral.

**cbBTC.** On a March 2020 path the queue takes 12 hours to clear at the median under observed capacity, and BTC's worst 12 hours were -38%. No LLTV in the plausible range covers that fully; the question is how much loss is tolerable, and under what depth assumption. At 86% the worst path costs 1.5% of supply if depth holds at 30%, and 4-5% if it collapses the way it did in October 2025; that is four months to a year of supplier interest, borne by USDC depositors. At 80% the worst path costs 0.4% under the base assumption and every other path is clean. If Coinbase commits to redeem-and-sell as liquidator of last resort, 86% becomes defensible (1.2% worst case, oracle risk only) and that commitment should be published, because lenders are pricing it whether it exists or not. Comparators: Aave sets cbBTC on Base at a 78% liquidation threshold; Ledn liquidates at 80%; Unchained at 83% with a 24-hour cure period.

**Pre-liquidation, whichever LLTV is chosen.** Section 3 shows the margin-call flow pushing marginal positions onto the cliff. Morpho supports pre-liquidation contracts: a band (say 80-86% LTV) where positions can be partially closed at a small bonus (1-2%) before the hard line. That drains the queue during the slide, when capacity is idle, instead of at the cliff. It converts Coinbase's warning cadence from a lender risk into a lender protection, and it costs borrowers less than a 4.38% full liquidation.

**WETH.** 77%. Same as Coinbase already uses for cbETH, and the only setting in the grid that survives all seven paths under every scenario. The cost is small: the market is $83M.

**Alts at 62.5%.** The volatility buffer is adequate: the bad-debt line is a further 29.6% below the liquidation line, and the worst observed 4-hour moves are -31% (XRP, Mar 2020), -35% (XRP, Oct 2025), -37% (DOGE, Oct 2025), -34% (SOL, FTX). What is missing is a size rule. There is no on-chain venue for cbXRP, cbDOGE, cbADA or cbLTC on Base; every seized unit must be redeemed through Coinbase and sold on Coinbase's book. Coinbase's own XRP and SOL books hold $8-10M within 10% of mid, against a 12.7% bonus at this LLTV. A per-asset cap of the form "debt that would be liquidatable at -30% must not exceed one hour of Coinbase's own depth" keeps these markets in the regime where the backtest says 62.5% is safe. cbXRP at $48M is the one to watch.

## 6. What this does not capture

- Depth in a crash is a guess scaled from today. We do not buy historical order books. The sensitivity paragraph is the honest statement of that uncertainty, and it spans a factor of ten.
- The March 2020 replay drops a 2026-sized book onto 2020 prices. BTC's market is far deeper now; it is also true that Oct 10 2025 produced the thinnest books Kaiko has ever measured.
- Borrower response is fit on three events with two parameters, absorbs other model error, and assumes Coinbase's warning cadence stays as it is. The model seizes in full; real liquidations are mostly partial.
- Whether Coinbase liquidates its own book is unverified. It is the single largest swing factor in the results.
- Oracle behaviour is modeled as a one-bar lag on Coinbase's candle low. The Chainlink path on Base tracked the exchange low within 0.1% on the lived events, so this is mild.

## Sources

Morpho Blue API and contracts on Base; Coinbase Exchange public candles and L2 book; Chainlink BTC/USD and ETH/USD aggregators on Base; Morpho's Coinbase Dune dashboards; Kaiko research on Oct 2025 and March 2020 depth; Chaos Labs' Aave risk methodology; Basel SCO60. Full citations in `research/`.
