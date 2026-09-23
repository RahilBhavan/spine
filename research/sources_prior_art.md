# Prior art and haircut benchmarks, 2026-09-15 (researcher sweep)

## Existing dashboards / analyses
- Morpho Dune "Coinbase Crypto Backed Loans - Liquidations Dashboard": https://dune.com/morpho/coinbase-on-chain-loan-positions-liquidations-dashboard . Has oracle price, histograms by liquidation price and drawdown bucket, Coinbase vs non-Coinbase, liquidation timeline, stress table: -5% $1.28M (0.09%); -15% $55M (4.0%, 3,046 users); -30% $315M (23%); -50% $1.10B (80%).
- Morpho Dune "Coinbase Onchain Borrowing & Lending": https://dune.com/morpho/coinbase-onchain-lending-borrowing . Collateral 2026-09-15: cbBTC/USDC 86% $2.80B, WETH/USDC 86% $179M, cbXRP/USDC 62.5% $138M, cbETH/USDC 77% $27M, SOL/USDC 62.5% $15M.
- rudexxx cbBTC/USDC: https://dune.com/rudexxx/cbbtc-usdc-morpho-blue-base (largest borrower $136M per its table; check). ryanyyi: https://dune.com/ryanyyi/coinbase-onchain-loans (broken).
- Steakhouse update 2026-07-02: https://kitchen.steakhouse.financial/p/defi-markets-update-2026-07-02
- becausebitcoin Feb 2026 analysis: https://becausebitcoin.com/post/coinbase-defi-loans-record-liquidations-btc-eth-slide-morpho-analysis
- The Block $1B: https://www.theblock.co/post/373032/coinbase-tops-1-billion-in-bitcoin-backed-onchain-loans-via-morpho ; Morpho $5B on Base: https://morpho.org/blog/5b-on-base-is-the-new-day-one-for-onchain-finance
- No Gauntlet/Block Analitica/Chaos report on this market found.

## How curators set LLTV
- Morpho: whitelisted LLTV list, no published quantitative rule; LIF formula only. https://docs.morpho.org/learn/concepts/liquidation/
- Chaos Labs methodology: VaR = p99 of 24h protocol loss from underwater accounts; maximize E[profit]/VaR s.t. VaR <= K; GARCH(1,1) paths; agent-based liquidators with simulated DEX slippage; stressed VaR for black swans. https://chaoslabs.xyz/resources/chaos_aave_risk_param_methodology.pdf
- Chaos WBTC LT cut 78 -> 73-76%: https://governance.aave.com/t/arfc-chaos-labs-risk-parameter-updates-wbtc-parameter-adjustments/19118
- Aave cbBTC Base: 73% LTV / 78% LT / 7.5% penalty. https://app.aave.com/reserve-overview/?underlyingAsset=0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf&marketName=proto_base_v3 ; Llama Risk note https://web.archive.org/web/20250911152740/https://www.llamarisk.com/research/2024-09-13T16%3A07%3A47.000Z (archived) ; Aave risk doc https://github.com/aave/risk-v3/blob/main/asset-risk/risk-parameters.md
- Gauntlet methodology (inputs only): https://www.gauntlet.xyz/resources/under-the-hood-unpacking-our-morpho-vault-curation-methodology
- RiskDAO SmartLTV: LTV = exp(-c*sigma/sqrt(l/d)) - beta; c calibrated 1.17 (Jan 2020), 2.58 (Feb 2021), 5.99 (Mar 2020). https://docs.bprotocol.org/risk-oracle/smartltv-formula

## TradFi benchmarks
- Basel SCO60 (in force 2026-01-01): Group 2 crypto not eligible collateral (SCO60.30); 30% haircut for crypto lent in SFTs (SCO60.94); 1%/2% Tier 1 exposure limit (SCO60.117); 1250% RW Group 2b; SCO60.29 requires assessing liquidation period and downturn liquidity depth. https://www.bis.org/basel_framework/chapter/SCO/60.htm?inforce=20260101&published=20240717
- Ledn 50/70/80; Unchained 40-50/67/83 with 24h cure (https://bitmachina.ca/en/articles/ledn-vs-unchained); SALT 70/75/83.33 (https://www.spark.money/research/bitcoin-collateralized-lending-compared). Cantor/Galaxy/Sygnum: undisclosed.
- CME Micro BTC maintenance ~35% (https://www.cmegroup.com/education/articles-and-reports/how-to-trade-micro-bitcoin-futures); 47%/43% at Dec 2017 launch. Crash-period history unverified.

## Morpho bad debt precedents
- BTC/USDC markets: ~$0 on >$500M liquidations (Steakhouse).
- sdeUSD/USDC ~3.6% of MEV Capital vault, Nov 2025 (https://x.com/MEVCapital/status/1988581694476071222); PAXG/USDC oracle misconfig $230k Oct 2024 (https://medium.com/coinmonks/decoding-morphoblues-230k-exploit-6296565ced40). Both oracle/stablecoin failures.
- Realized cbBTC liquidation slippage in stress: no published figure.

## Framing
- "1 - LLTV >= worst N-hour move at 99% (stressed vol) + liquidation bonus/slippage at book-relevant size + oracle lag", with N from time-to-liquidate. Anchor: 14% buffer absorbed -17%/-26% weekly moves with no bad debt; 23% of book liquidates at -30%.
