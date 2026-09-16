# What haircut should Coinbase take on BTC and ETH collateral?

*Spine, 2026-09-15. Every number here is produced by a script in this repo from public data: the Morpho API, Base RPC, Coinbase Exchange, and Chainlink logs. The dashboard refreshes hourly. Backtest and calibration outputs are in `data/backtest.json` and `data/calibration.json`.*

## The short version

Coinbase lends USDC against cbBTC and ETH on Morpho (Base) at an 86% liquidation LTV with a 4.38% liquidation bonus. The book is $1.41B of debt against $2.86B of cbBTC, 39,000 positions, 97.5% of it Coinbase Smart Wallets. It has been through three real stress events (Oct 2025, Feb 2026, Jun 2026), cleared $256M of liquidations in the four stress weeks alone, and taken zero bad debt.

That record is real and it is also not the test. Replaying the book through March 2020 and May 2021 shows the 86% line holds only if Coinbase itself stands behind liquidations. Recommended haircuts:

| Collateral | Today (LLTV / max draw) | Recommended | Why |
|---|---|---|---|
| cbBTC | 86% / 75% | **80% / 70%**, or keep 86% only with a disclosed backstop liquidator | March 2020 replay: $64M bad debt (4.1% of supply) at 86% with observed liquidator capacity; $25M (1.6%) at 80%; $20M at 86% even with unlimited depth, from oracle jumps |
| WETH | 86% / 75% | **77% / 70%** | ETH's 5-minute moves exceed the 4.38% bonus; at 86% three of seven crashes leave bad debt even with unlimited depth. At 77%, none do. cbETH already sits at 77% |
| cbXRP, SOL, cbDOGE, cbADA, cbLTC, JitoSOL | 62.5% / 55% | **62.5%**, plus a per-asset book cap tied to Coinbase's own order-book depth | The 26-point buffer to the bad-debt line covers the worst observed 4-hour moves (-31% to -37%). The constraint is disposal: none of these have a venue on Base, so every liquidation routes through Coinbase redemption |

The lever that matters is not the origination cap, it is the liquidation LTV, because on Morpho a lower LLTV also raises the liquidation bonus. At 86% a liquidated position is underwater after a further 10.2% drop; at 80% after 14.5%; at 77% after 16.5%. March 2020's worst four hours were -35%.

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

We model this as a responsive share of borrowers who repay to 74% LTV once they have spent a reaction time inside the warning zone (80-86% LTV). Fitting the share and the delay on the three cbBTC events gives 70% responsive and a two-hour reaction, and reproduces all three within 15% (Feb 1.03x, Jun 0.85x, Oct 0.95x). Held-out WETH comes in at 1.58x and 0.85x. Two parameters on three events deserves modest confidence; the qualitative point is robust.

What the fit buys is time-dependence. Median warning time between entering the 80-86% zone and crossing 86%:

| Crash | Warning time for the median liquidated position |
|---|---|
| Feb 2026 | 22 hours |
| Jun 2026 | 41 hours |
| Oct 2025 | 86 hours |
| Aug 2024 | 8 hours |
| May 2021 | 8 hours |
| **Mar 2020** | **20 minutes** |

Coinbase's borrower-warning flow works because crashes so far have been slow. It cannot work on a Black Thursday shape.

One uncomfortable result: partial borrower response can raise bad debt. On the March 2020 path, marginal positions that would have been liquidated early, when the queue was empty, top up just enough to stay out, then fall in together on the cliff day. At 77-80% LLTV the responsive book loses more than the passive one on that path, and a four-hour reaction time makes 86% worse than no response at all.

## 4. The backtest

Today's cbBTC book is dropped onto each historical path from its pre-crash peak at 5-minute resolution. Positions over LLTV enter a queue served largest-first. Liquidator capacity per step comes from measured depth times a stress multiplier (DEX 0.5, CEX 0.3) with 20% replenishment per step. Bad debt is the shortfall on positions whose LTV passes 1/LIF (95.8% at 86% LLTV) before they clear, realized or still sitting at the trough. Three capacity scenarios:

- **A**: on-chain bots only (Base DEX depth).
- **AB**: plus liquidators who seize cbBTC and sell BTC on Coinbase and Kraken. This matches observed behaviour.
- **ABC**: plus Coinbase itself redeeming cbBTC 1:1, effectively unlimited depth at the exchange price. Whether Coinbase runs such a liquidator is not public.

cbBTC at today's terms (86% / 75%), borrower response on:

| Path | Worst 4h / 24h | AB: liquidated | AB: bad debt | AB: queue p50 / p95 | ABC: bad debt |
|---|---|---|---|---|---|
| Mar 2020 | -35% / -50% | $1,052M | **$64M (4.1%)** | 12 h / 4 days | $20M (1.2%) |
| May 2021 | -26% / -32% | $449M | **$17M (1.1%)** | 35 min / 4 days | $0.8M |
| FTX Nov 2022 | -15% / -19% | $99M | 0 | 0 / 10 min | 0 |
| Aug 2024 | -11% / -20% | $132M | 0 | 0 / 6 h | 0 |
| Oct 2025 | -10% / -13% | $35M | 0 | 0 / 5 min | 0 |
| Feb 2026 | -9% / -18% | $159M | 0 | 0 / 0 | 0 |
| Jun 2026 | -7% / -9% | $44M | 0 | 0 / 0 | 0 |

Percentages are of the $1.57B USDC supplied to the market. Bad debt on Morpho is socialized to suppliers, which includes depositors in the Coinbase USDC lending product, not Coinbase's balance sheet.

Bad debt across the LLTV grid, cbBTC, scenario AB, max draw 75%:

| LLTV | Bad-debt LTV (1/LIF) | Mar 2020 | May 2021 | Other five |
|---|---|---|---|---|
| 86% | 95.8% | $64M | $17M | 0 |
| 80% | 93.6% | $25M | $0.5M | 0 |
| 77% | 92.2% | $14M | 0 | 0 |
| 70% | 89.6% | $0.2M | 0 | 0 |
| 62.5% | 88.7% | 0 | 0 | 0 |

With a Coinbase backstop (ABC), 77% clears every path with zero bad debt, and 86% leaves $20M on March 2020 that no amount of depth removes: it is the gap between two 5-minute oracle updates exceeding the bonus.

Sensitivity that matters: the CEX depth multiplier. At 86% on March 2020, k_cex 0.1 gives $180-200M of bad debt (12% of supply), 0.3 gives $64M, 1.0 gives $3-6M. Kaiko measured top-of-book BTC depth falling more than 90% intraday on Oct 10 2025. Assuming 30% of today's depth survives a Black Thursday is not conservative. Oracle lag and DEX depth move results by single-digit millions.

Without borrower response (the upper bound): March 2020 AB bad debt is $68M and Feb 2026 liquidations would have been $456M instead of the realized $151M.

WETH at 86% / 75%: March 2020 $0.9M, May 2021 $0.3M, Aug 2024 $0.3M of bad debt under every scenario including unlimited depth (about 1% of that market's supply at worst). WETH's problem is not depth (Base has $26M+ of WETH-to-USDC capacity at 4.38%), it is that ETH gaps more than 4.38% inside five minutes. At 77% every path is clean.

## 5. The argument, in one line per asset

The rule: **1 - LLTV must cover the worst move over the time it takes to clear the queue, plus the liquidation bonus, plus one oracle interval.** Basel's SCO60.29 says the same thing in regulator language: assess the liquidation period and downturn liquidity depth before recognizing crypto collateral.

**cbBTC.** Queue clearance on a March 2020 path takes 12 hours at the median under observed capacity, and BTC's worst 12 hours were -38%. No LLTV in the plausible range covers that fully; the question is how much loss is tolerable and who pays. At 80% the worst-path loss falls to 1.6% of supply and every other path is clean. At 86% the worst path costs 4.1% of supply, roughly a year of interest, borne by USDC depositors. If Coinbase commits to redeem-and-sell as liquidator of last resort, 86% becomes defensible (1.2% worst case) and that commitment should be published, because lenders are pricing it whether it exists or not. TradFi comparators: Aave sets cbBTC on Base at 78% liquidation threshold; Ledn liquidates at 80%; Unchained at 83% with a 24-hour cure period.

**WETH.** 77%. Same as Coinbase already uses for cbETH, and the only setting in the grid that survives all seven paths under every scenario. The cost is small: the market is $83M.

**Alts at 62.5%.** The volatility buffer is adequate: the bad-debt line is a further 29.6% below the liquidation line, and the worst observed 4-hour moves are -31% (XRP, Mar 2020), -35% (XRP, Oct 2025), -37% (DOGE, Oct 2025), -34% (SOL, FTX). What is missing is a size rule. There is no on-chain venue for cbXRP, cbDOGE, cbADA or cbLTC on Base; every seized unit must be redeemed through Coinbase and sold on Coinbase's book. Coinbase's own XRP and SOL books hold $8-10M within 10% of mid, against a 12.7% bonus at this LLTV. A per-asset cap of the form "debt that would be liquidatable at -30% must not exceed one hour of Coinbase's own depth" keeps these markets in the regime where the backtest says 62.5% is safe. cbXRP at $48M is the one to watch.

## 6. What this does not capture

- Depth in a crash is a guess scaled from today. We do not buy historical order books. The sensitivity table is the honest statement of that uncertainty.
- The March 2020 replay drops a 2026-sized book onto 2020 prices. BTC's market is far deeper now; it is also true that Oct 10 2025 produced the thinnest books Kaiko has ever measured.
- Borrower response is fit on three events with two parameters and assumes Coinbase's warning cadence stays as it is.
- Whether Coinbase liquidates its own book is unverified. It is the single largest swing factor in the results.
- Oracle behaviour is modeled as a one-bar lag on Coinbase's candle low. The Chainlink path on Base tracked the exchange low within 0.1% on the lived events, so this is mild.

## Sources

Morpho Blue API and contracts on Base; Coinbase Exchange public candles and L2 book; Chainlink BTC/USD and ETH/USD aggregators on Base; Morpho's Coinbase Dune dashboards; Kaiko research on Oct 2025 and March 2020 depth; Chaos Labs' Aave risk methodology; Basel SCO60. Full citations in `research/`.
