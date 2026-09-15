# Stress-event and liquidity data sources, 2026-09-15 (researcher sweep)

## Free OHLCV (probed)
- Coinbase Exchange candles: 1m back to Mar 2020 for BTC-USD and ETH-USD; granularity {60,300,900,3600,21600,86400}; 300/call; 10 req/s; no key. https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles
- Bitstamp /api/v2/ohlc/{pair}/?step=60&limit=1000&start= ; no key. https://www.bitstamp.net/api/
- Bitfinex api-pub.bitfinex.com/v2/candles/trade:1m:tBTCUSD/hist limit 10000. https://docs.bitfinex.com/reference/rest-public-candles
- Binance REST geo-blocked from US; monthly zips work: https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1m/BTCUSDT-1m-2020-03.zip
- Kraken REST OHLC only last 720 candles; use quarterly CSV zips (https://support.kraken.com/hc/en-us/articles/360047124832, unverified).
- Coinbase L2 book: /products/BTC-USD/book?level=2 full aggregated (~20k levels each side); level=3 raw.

## Crash table (Coinbase 5m; worst high-to-low within window; recovery = first daily high >= prior peak)
| Window | Asset | Peak | Trough | P2T | 1h | 4h | 24h | Recovery |
| Mar 2020 | BTC | 9,215 (03-07) | 3,858 (03-13 02:15) | -58.1% | -24.4% | -34.9% | -50.3% | 48d |
| | ETH | 253 | 90 | -64.4% | -25.2% | -32.6% | -51.9% | 81d |
| May 2021 | BTC | 59,592 | 30,000 (05-19 13:10) | -49.7% | -22.8% | -26.1% | -31.9% | 148d |
| | ETH | 4,384 | 1,860 | -57.6% | -32.3% | -38.0% | -46.4% | 162d |
| FTX 2022 | BTC | 21,479 | 15,512 (11-09 22:05) | -27.8% | -8.1% | -15.3% | -18.6% | 68d |
| | ETH | 1,677 | 1,071 | -36.1% | -12.3% | -22.3% | -28.1% | 72d |
| Aug 2024 | BTC | 70,000 | 49,050 (08-05 06:20) | -29.9% | -10.0% | -11.3% | -19.7% | 84d |
| | ETH | 3,397 | 2,116 | -37.7% | -21.5% | -23.1% | -27.9% | 99d |
| Oct 2025 | BTC | 126,296 (10-06) | 107,000 (10-10 21:25) | -15.3% | -8.7% | -9.5% | -12.7% | none |
| | ETH | 4,759 | 3,510 | -26.2% | -12.8% | -14.6% | -20.2% | none |
| Feb 2026 | BTC | 90,477 (01-28) | 60,001 (02-06 00:10) | -33.7% | -7.2% | -9.3% | -18.0% | none |
| | ETH | 3,042 | 1,743 | -42.7% | -9.2% | -12.2% | -19.7% | none |
| Jun 2026 | BTC | 67,264 (06-15) | 57,718 (07-01) | -14.2% | -5.3% | -5.9% | -6.6% | 49d |
| | ETH | 1,848 | 1,505 (06-06) | -18.3% | -6.6% | -7.1% | -8.9% | 18d |
- Cycle drawdown: BTC 126,296 (2025-10-06) -> 57,718 (2026-07-01), -54.3%, 268d. ETH -68.4%. Other venues printed lower Oct 10 wicks (CoinGecko: 104,782). https://www.coingecko.com/learn/october-10-crypto-crash-explained
- Script: research/crash_table.py

## Order book depth
- Live: Coinbase L2 (above); Binance /api/v3/depth limit 5000 (US-blocked); Kraken /0/public/Depth count<=500.
- Historical (paid): Tardis.dev ($350-6,000/mo; first day of month free), Kaiko (sales), CoinAPI, Coinbase L2 tick history (data.coinbase.com).
- Published stress numbers: Oct 10 2025 Kaiko: top-of-book depth down >90% intraday; Binance 0.01 BTC bid at 0.1%, Coinbase 0.00 at 0.1%, 6.07 BTC at 10%; aggregated 2% depth down ~30% from 2025 high (https://www.fticonsulting.com/insights/articles/crypto-crash-october-2025-leverage-met-liquidity, https://cryptoslate.com/bitcoin-struggles-to-reclaim-90000-amid-plummeting-liquidity-and-waning-market-depth/). Mar 2020 Kaiko: "barely any bids 0-2% from mid" in first minutes (https://blog.kaiko.com/how-black-thursday-decimated-cryptocurrency-order-books-58167bf9157d). FTX: 2% depth roughly halved, "Alameda gap". Aug 2024: US slippage tripled within hours. May 2021: unverified.

## cbBTC liquidity on Base (GeckoTerminal/DefiLlama)
| Pool | Address | TVL | 24h vol |
| Aerodrome Slipstream cbBTC/USDC 0.05% | 0x4e962bb3889bf030368f56810a9c96b83cb3e778 | $5.7M | $14.3M |
| Aerodrome Slipstream USDC/cbBTC 1% CL2000 | 0x3e66e55e97ce60096f74b7c475e8249f2d31a9fb | $7.0M | $7.2M |
| Aerodrome Slipstream cbBTC/USDC 0.05% v3 | 0x160d7e9d948b16c163332a277b393c288408eb12 | $4.0M | $34.8M |
| Uniswap v3 cbBTC/USDC 0.05% | 0xfbb6eed8e7aa03b138556eedaf5d271a5e1e43ef | $7.5M | $11.2M |
| Uniswap v4 cbBTC/USDC 0.05% | poolId 0x12d76c5c...8e078 | $4.2M | $3.8M |
| Aerodrome cbBTC/WETH 0.05% | 0x70acdf2ad0bf2402c957154f944c19ef4e1cbae1 | $14.6M | $4.7M |
| Aerodrome cbBTC/WETH 0.05% v3 | 0x42d4a22cad0f5a49681a5715ce994af73a43b76b | $10.1M | $40.7M |
| Uniswap v3 cbBTC/WETH 0.3% / 0.05% | 0x8c7080564b5a792a33ef2fd473fba6364d5495e5 / 0x7aea2e8a3843516afa07293a10ac8e49906dabd1 | $11.1M / $8.6M | |
- Quoters: Aerodrome Slipstream QuoterV2 0x254cF9E1E6e233aa1AC962CB9B05b2cfeAaE15b0 (tickSpacing arg); Uniswap v3 QuoterV2 Base 0x3d4e44Eb1374240CE5F1B871ab261CD16335B76a; v4 Quoter 0x0d5e0F971ED27FBfF6c2837bf31316121532048D (unverified today).
- Liquidator disposal DEX vs redeem: unverified. Flash-loan liquidators must sell on DEX (redemption is non-atomic).

## Realized events on the market
- Oct 10-11 2025: protocol-wide Morpho liquidations ~$100M (https://cryptorank.io/insights/analytics/crypto-market-crash-2025-10-11-overview); Base cbBTC split unverified; bad debt 0.
- Feb 2026 week: ~$170M Coinbase-user collateral liquidated, $90.7M / ~2,000 users on Feb 5 (https://decrypt.co/357265/coinbases-loans-record-liquidations-bitcoin-ethereum-plunge, https://becausebitcoin.com/post/coinbase-defi-loans-record-liquidations-btc-eth-slide-morpho-analysis). Coinbase warns users every 30 min; bots act in seconds.
- Jun 2-5 2026: ~$57.3M / 3,784 users; Jun 25: $9.45M (BTC low $58.2k). Steakhouse: ~$394M liquidated on Base cbBTC/USDC since Nov 2025, no realized bad debt (https://kitchen.steakhouse.financial/p/defi-markets-update-2026-07-02).
- Dune per-liquidation query: https://dune.com/changhao/morpho-liquidation-base
