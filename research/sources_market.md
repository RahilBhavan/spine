# Coinbase x Morpho (Base) fact sheet, 2026-09-15 (researcher sweep, verified via blue-api.morpho.org + mainnet.base.org)

## Primary market
- Morpho Blue core Base: 0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb (https://docs.morpho.org/get-started/resources/addresses/)
- cbBTC/USDC 86%: 0x9103c3b4e834476c9a62ea009ba2c884ee42e94e6e314a26f04d312434191836; loan USDC 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913, collateral cbBTC 0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf, oracle 0x663BECd10daE6C4A3Dcd89F1d76c1174199639B9 (MorphoChainlinkOracleV2 over Chainlink BTC/USD 0x64c911996D3c6aC71f9b455B1E8E7266BcbD848F, scaleFactor 1e26), IRM 0x46415998764C29aB2a25CbeA6254146D50D22687 (AdaptiveCurveIRM). Created 2024-09-04 block 19,326,981.
- State 2026-09-15: supply $1.571B, borrow $1.413B, collateral $2.860B, util 89.9%, borrow APY 4.76%, badDebt 0. 14,009 liquidation txs. 70,496 positions, 39,106 with borrowShares>=1.

## All Coinbase-linked markets (Base, loan USDC, same IRM)
- WETH 0x4200000000000000000000000000000000000006 86%: 0x8793cf302b8ffd655ab97bd1c695dbd967807e8367a65cb2f4edaf1380ba1bda, oracle 0xFEa2D58cEfCb9fcb597723c6bAE66fFE4193aFE4 (ETH/USD 0x71041dddad3595F9CEd3DcCFBe3D1F4b0a16Bb70 / USDC/USD 0x7e860098F58bBFC8648a4311b374B1D669a2bc6B), borrow $83M. ETH loans Nov 2025: https://www.theblock.co/post/379680/coinbase-eth-loans-morpho-up-to-1-million
- cbETH 0x2Ae3F1Ec7F1F5012CFEab0185bfc7aa3cf0DEc22 77%: 0x0ca10126f6c94cbd9cf0a48cc9516ae5e3dec5aa68303e6d988ee37c5149bf0d, oracle 0x97FF9CbD7E77348b2B8FfBB883bF29452aD18295 (CBETH/USD 0xd7818272B9e248357d13057AAb0B417aF31E817d), created 2025-12-10, borrow $11M. https://www.coindesk.com/markets/2026/01/23/coinbase-lets-users-borrow-up-to-usd1-million-against-staked-ether-without-selling
- cbXRP 0xcb585250f852C6c6bf90434AB21A00f02833a4af 62.5%: 0xd4a903dc6d949519060c7707f9604fdc9772c046e05c2e3a8fce0bd7196e4109, oracle 0x031b2EFC8d70042Ac8d9f5c793c4149eC4b60fdE (XRP/USD 0x9f0C1dD78C4CBdF5b9cf923a549A201EdC676D34), created 2026-01-15, borrow $48M.
- SOL 0x311935Cd80B76769bF2ecC9D8Ab7635b2139cf82 62.5%: 0x7dc02ff6c536b1d49d7fba770438d79f5bd1f1c78884629b7d1aaee19675782b, oracle 0xE9725430f3A72611ac72EdDc650625bce4F45DC7 (SOL/USD 0x975043adBb80fc32276CbF9Bbcfd4A601a12462D), created 2026-03-14, borrow $5.3M. https://www.theblock.co/post/400980/coinbase-solana-loans-morpho-borrow-100000
- cbDOGE 0xcbD06E5A2B0C65597161de254AA074E489dEb510 62.5%: 0x73527ddd796e6d4f48387adaae36f6f3d49d606d7f2a15eb0c931416a58875d8, oracle 0xA9D36600Fb9eba7548857e61F836Ec951e3091B2, created 2025-10-10.
- cbADA 0xcbADA732173e39521CDBE8bf59a6Dc85A9fc7b8c 62.5%: 0xd7520ad198b497b6eb75bc690268f4597630dbc12e305e9d4105843bab36e41d, oracle 0x35D87a743D1F2f7CaFb42D855dC1c5Df857Ce45f, created 2026-01-15.
- cbLTC 0xcb17C9Db87B595717C857a08468793f5bAb6445F 62.5%: 0x9125d0fa03c3137166df68bcc72283477830de2a4a5536512374c573ad4583c3, oracle 0x47f961E6653423A77b1EF8Fb680eE53bf7d8a00d, created 2025-10-10.
- JitoSOL 0x97bE14Dd8f994A5364573BC035D85309E7CB34de 62.5%: 0x09276541cfecb6920a80679a1deced4dde3ae64bf5fc2c9c1f9c21e0c152e1a5, oracle 0x78F772F5Fcc03256260cC1165e34Da9bb3f9BE1C, created 2026-05-15. Feed unverified.
- Older 77% cbXRP/cbADA markets (Oct 2025) exist with small balances; migration unverified.
- USDC lending product via Steakhouse-curated vaults: https://morpho.org/blog/morpho-is-now-powering-usdc-lending-on-coinbase/
- Dune list of markets: https://dune.com/morpho/coinbase-onchain-lending-borrowing

## Identifying Coinbase borrowers
- Shared public markets; no dedicated market. Borrowers are per-user Coinbase Smart Wallets (ERC-4337).
- Factories: v1.0 0x0BA5ED0c6AA8c49038F819E587E2633c4A9F428a (impl 0x000100abaad02f1cfC8Bbe32bD5a564817339E72), v1.1 0xBA5ED110eFDBa3D005bfC882d75358ACBbB85842 (impl 0x00000110dCdEdC9581cb5eCB8467282f2926534d). https://github.com/coinbase/smart-wallet/releases
- Verified check: ERC-1967 impl slot 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc of borrower address; top two borrowers resolve to v1.1 impl; a liquidated EOA returns 0.
- Paymaster (gas in cbBTC) and Magic Spend: https://morpho.org/stories/coinbase/

## Product terms
- Max draw LTV 75%, liquidation 86% (https://www.theblock.co/post/379680/...); one source says 70% (https://finance.yahoo.com/news/coinbase-joins-billion-dollar-lending-112054652.html). Coinbase help pages 403 to fetch.
- Penalty 4.38% = 1/(0.3*0.86+0.7)-1.
- Limits: $100k (Jan 2025) -> $1M (Apr 2025) -> $5M BTC; $1M ETH; $100k SOL/ADA/XRP/LTC/DOGE (https://help.coinbase.com/en/coinbase/trading-and-funding/loan/collateral).
- Originations: $1B Oct 2025 (https://www.theblock.co/post/373032/coinbase-tops-1-billion-in-bitcoin-backed-onchain-loans-via-morpho); $2.17B BTC / $2.3B all by May 2026; $1.3B outstanding on $2.5B cbBTC Aug 2026 (https://morpho.org/blog/5b-on-base-is-the-new-day-one-for-onchain-finance).

## Data access
- GraphQL https://blue-api.morpho.org/graphql (also api.morpho.org/graphql), no key, 750 req/min, complexity cap 1e6, first<=1000, skip<=10000. https://docs.morpho.org/tools/offchain/api/get-started/
- marketPositions filters: marketUniqueKey_in, chainId_in, userAddress_in, borrowShares_gte/lte, healthFactor_gte/lte, collateral_gte/lte. Fields: user{address} healthFactor state{collateral borrowAssets borrowAssetsUsd collateralUsd}.
- marketTransactions(where:{marketUniqueKey_in, chainId_in:[8453], type_in:[Liquidation]}) { items { txHash timestamp blockNumber user{address} data{ ... on MarketTransactionLiquidationData { liquidator repaidAssets repaidShares seizedAssets badDebtAssets badDebtShares } } } }
- marketCollateralAtRisk(uniqueKey, chainId, numberOfPoints) -> collateralPriceRatio/collateralUsd curve.
- Historical position snapshots unreliable; rebuild from events.
- Event topic0 (from EventsLib.sol):
  Supply 0xedf8870433c83823eb071d3df1caa8d008f12f6440918c20d75a3602cda30fe0
  Withdraw 0xa56fc0ad5702ec05ce63666221f796fb62437c32db1aa1aa075fc6484cf58fbf
  Borrow 0x570954540bed6b1304a87dfe815a5eda4a648f7097a16240dcd85c9b5fd42a43
  Repay 0x52acb05cebbd3cd39715469f22afbf5a17496295ef3bc9bb5944056c63ccaa09
  SupplyCollateral 0xa3b9472a1399e17e123f3c2e6586c23e504184d504de59cdaa2b375e880c6184
  WithdrawCollateral 0xe80ebd7cc9223d7382aab2e0d1d6155c65651f83d53c8b9b06901d167e321142
  Liquidate 0xa4946ede45d0c6f06a0f5ce92c9ad3b4751452d2fe0e25010783bcab57a67e41
  AccrueInterest 0x9d9bd501d0657d7dfe415f779a620a62b78bc508ddc0891fbbd8b7ac0f8fce87
- RPC getLogs ranges: mainnet.base.org 2,000 blocks; base.drpc.org 10,000; publicnode refuses archive; QuickNode free 5.
- Dune decoded tables follow morpho_blue_<chain>.morphoblue_evt_<event> (Base names unverified). Example liquidation query https://dune.com/queries/4216704

## Liquidation mechanics
- LIF = min(1.15, 1/(0.3*LLTV+0.7)) (https://docs.morpho.org/learn/concepts/liquidation/, ConstantsLib.sol). 86% -> 1.04384; 77% -> 1.0846; 62.5% -> 1.1274.
- Bad debt: collateral 0 with debt left -> written off, socialized to suppliers; emitted as badDebtAssets. Vault v1.1 does not auto-realize. https://docs.morpho.org/curate/tutorials-v1/bad-debt/
- cbBTC redeemable 1:1 via Coinbase account (non-atomic): https://www.coinbase.com/blog/coinbase-wrapped-btc-cbbtc-is-now-live
