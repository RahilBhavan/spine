# Does Coinbase liquidate its own Morpho book? (researched 2026-09-19)

**Answer: no on the public record; unverified on-chain, but every top liquidator looks independent.**

## Public statements
- Morpho launch post: liquidators "can step in automatically, without requiring Coinbase's direct involvement, to prevent bad debt." https://morpho.org/blog/pioneering-the-defi-mullet-coinbase-in-the-front-defi-in-the-back
- Coinbase Help (collateral page): "Coinbase cannot prevent your collateral from being liquidated on Morpho"; liquidation at 86%; remaining BTC returned to the user's account. https://help.coinbase.com/en/coinbase/trading-and-funding/loan/collateral
- Decrypt, 6 Feb 2026: liquidations done by third parties; Coinbase spokesperson: "Coinbase doesn't earn any fees from users' liquidations"; warnings up to every 30 minutes. No backstop language. https://decrypt.co/357265/coinbases-loans-record-liquidations-bitcoin-ethereum-plunge
- DeFi Lend (Steakhouse vaults): not deposits, not FDIC/SIPC insured, "may lose value"; liquidation-failure losses shared pro rata. https://help.coinbase.com/en/coinbase/trading-and-funding/loan/lending-intro , https://www.coinbase.com/legal/insurance
- Steakhouse Feb 2026 write-up: contracts auction collateral to "arbitrageurs"; "Risk cannot be removed". https://kitchen.steakhouse.financial/p/238m-liquidations-of-onchain-lending
- SEC EDGAR full-text 2025-2026: "Morpho" appears in no Coinbase 10-K/10-Q; "crypto-backed loans" only in 8-K shareholder letters as product updates.
- Morpho's Coinbase Dune dashboard has no liquidator breakdown. Morpho Effect Feb/Jun 2026 name no liquidator.

## On-chain (top 8 liquidators across Oct 2025 / Feb 2026 / Jun 2026 stress weeks, cbBTC/USDC)
| Liquidator | Share | Code | Creator | Created |
|---|---|---|---|---|
| 0xD12810B19B596347a3AFAC206d3cA65d08594b3f | 13% | EIP-1967 proxy | 0x4984...832F (unlabeled) | ~May 2024 |
| 0x9bE62980818c59fc654C5Ede5427EBAA32C7eb81 | 9% | 23,272 B | 0xd685...524a | 2025-11-27 |
| 0x312D2779E6a8E1701B134Ac3129a7f97Edf05a11 | 8% | 21,083 B | 0x4E1B...2F37 | 2026-02-04 |
| 0x23605743F312DE70924F4153560E256736745Ed6 | 8% | 21,778 B | 0x056c...9f8E | ~2026-01-31 |
| 0x119F163ad76e320bf264631491fdb711fA793B85 | 8% | 23,272 B (same bytecode as 0x9bE6) | 0x3640...6A82 | 2025-12-03 |
| 0x3d7BEe81047D11FE2C85E6E9ecbf82E4Deb18F54 | 7% | 13,765 B | 0x7C94...D2BD | ~2026-01-23 |
| 0xb05F53e20e61A20711cA2d654161f3787FcFb29A | 6% | 13,765 B (same as 0x3d7B) | 0xbE44...55ad | ~2026-02-01 |
| 0xFc92f12791C72b3eE0461A90D0410590513873C7 | 5% | 23,272 B (same as 0x9bE6) | 0x48B7...eE8c, funded by MEXC | 2025-11-27 |
- No Basescan name tags; no Coinbase-labeled creators or funders. Eight addresses are 5-6 operators (shared bytecode).
- Collateral flow checked for 0x9bE6: cbBTC from Morpho goes straight to Uniswap V3 cbBTC/WETH pool 0x8c7080564B5A792A33Ef2FD473fbA6364d5495e5 in the same tx (DEX sale, not Coinbase redemption). Others unverified.

## Precedents
No Morpho curator or originator has publicly committed to a backstop liquidator (unverified beyond search). Morpho describes liquidation as permissionless only.
