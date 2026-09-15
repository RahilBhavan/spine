"""Live liquidity snapshot: Coinbase L2 + Kraken books, Uniswap/Aerodrome quotes on Base -> data/depth.json."""
import json, os, time, datetime as dt, urllib.request
from spine.api import coinbase_get, rpc, UA

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'depth.json')
PRODUCTS = ['BTC-USD', 'ETH-USD', 'SOL-USD', 'XRP-USD', 'DOGE-USD', 'ADA-USD', 'LTC-USD']
KRAKEN = {'BTC-USD': 'XBTUSD', 'ETH-USD': 'ETHUSD'}
PCTS = [0.5, 1, 2, 3, 4.38, 5, 7.5, 10]
CAP_PCTS = [1, 2, 3, 4.38]

USDC = '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913'
UNIV3_QUOTER = '0x3d4e44Eb1374240CE5F1B871ab261CD16335B76a'
AERO_QUOTER = '0x254cF9E1E6e233aa1AC962CB9B05b2cfeAaE15b0'
# 4-byte selectors (stdlib has no keccak; verified with `cast sig`). Both are QuoterV2-style, returning (amountOut, sqrtPriceAfter, ticksCrossed, gas).
UNIV3_SEL = 'c6a5026a'  # quoteExactInputSingle((address,address,uint256,uint24,uint160))
AERO_SEL = '9e7defe6'   # quoteExactInputSingle((address,address,uint256,int24,uint160))
# name -> (quoter, selector, fee-or-tickSpacing)
POOLS = {'univ3_500': (UNIV3_QUOTER, UNIV3_SEL, 500), 'univ3_3000': (UNIV3_QUOTER, UNIV3_SEL, 3000),
         'aero_100': (AERO_QUOTER, AERO_SEL, 100), 'aero_2000': (AERO_QUOTER, AERO_SEL, 2000)}
DEX_ASSETS = {
    'cbBTC': dict(addr='0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf', decimals=8, cb_product='BTC-USD',
                  sizes=[0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500]),
    'WETH': dict(addr='0x4200000000000000000000000000000000000006', decimals=18, cb_product='ETH-USD',
                 sizes=[10, 50, 100, 250, 500, 1000, 2000, 5000, 10000]),
}


def book_depth(bids, asks):
    """bids/asks: [(price, size)] floats. Returns mid and bid-side USD depth within each pct of mid."""
    mid = (bids[0][0] + asks[0][0]) / 2
    return dict(mid=mid, bid_depth_usd={str(p): sum(px * sz for px, sz in bids if px >= mid * (1 - p / 100)) for p in PCTS})


def coinbase_book(product):
    b = coinbase_get(f'/products/{product}/book', level=2)
    return book_depth([(float(p), float(s)) for p, s, _ in b['bids']], [(float(p), float(s)) for p, s, _ in b['asks']])


def kraken_book(pair):
    req = urllib.request.Request(f'https://api.kraken.com/0/public/Depth?pair={pair}&count=500', headers={'User-Agent': UA['User-Agent']})
    r = json.load(urllib.request.urlopen(req, timeout=60))
    if r.get('error'):
        raise RuntimeError(r['error'])
    b = next(iter(r['result'].values()))
    return book_depth([(float(p), float(s)) for p, s, _ in b['bids']], [(float(p), float(s)) for p, s, _ in b['asks']])


def quote(quoter, sel, token_in, amount_raw, fee, retries=3):
    """USDC out (raw units) or None on revert (pool missing). Any other failure is retried then raised:
    a transient RPC error must never be recorded as a shallow pool.
    Note: QuoterV2 does not revert on a drained pool; it returns a partial fill, so out_usd at oversized
    inputs is a partial fill, not a price (slippage just becomes huge, which is what capacity needs)."""
    # static tuple arg: the 5 words inline, each left-padded to 32 bytes; tickSpacing is positive so uint encoding is fine
    data = '0x' + sel + ''.join('%064x' % w for w in (int(token_in, 16), int(USDC, 16), amount_raw, fee, 0))
    for i in range(retries):
        try:
            time.sleep(0.25)  # public RPC rate limit
            r = rpc('eth_call', [{'to': quoter, 'data': data}, 'latest'])
            return int(r[2:66], 16) if len(r) >= 66 else None
        except RuntimeError as e:
            if 'revert' in str(e).lower():
                return None
            if i == retries - 1:
                raise
            time.sleep(1.5 ** i)


def dex_asset(asset, mid):
    """Slippage is measured against each pool's own smallest-size quote (no CEX/DEX basis);
    the Coinbase mid only converts sizes to USD."""
    a = DEX_ASSETS[asset]
    pools = {}
    for name, (quoter, sel, fee) in POOLS.items():
        pools[name], ref = {}, None
        for size in a['sizes']:
            raw = quote(quoter, sel, a['addr'], int(size * 10 ** a['decimals']), fee)
            if raw is None:
                pools[name][str(size)] = None
                continue
            out = raw / 1e6
            ref = ref or out / size  # sizes ascend, so the first quote is the pool's marginal price
            pools[name][str(size)] = dict(out_usd=out, slippage=1 - out / (size * ref))
    cap = {}
    for s in CAP_PCTS:
        ok = {name: [float(k) for k, q in pq.items() if q and q['slippage'] <= s / 100] for name, pq in pools.items()}
        cap[str(s)] = dict(usd=sum(max(v, default=0) * mid for v in ok.values()),
                           saturated=any(a['sizes'][-1] in v for v in ok.values()))  # largest size still fits: capacity is a floor
    return dict(pools=pools, capacity_usd_at_slippage=cap)


def fetch_all():
    cex = {'coinbase': {p: coinbase_book(p) for p in PRODUCTS},
           'kraken': {p: kraken_book(k) for p, k in KRAKEN.items()}}
    dex = {a: dex_asset(a, cex['coinbase'][DEX_ASSETS[a]['cb_product']]['mid']) for a in DEX_ASSETS}
    d = dict(fetched_at=dt.datetime.now(dt.timezone.utc).isoformat(), cex=cex, dex=dex)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w') as f:
        json.dump(d, f, indent=1)
    return d


if __name__ == '__main__':
    d = fetch_all()
    print(f"{'venue':9} {'asset':9} {'mid':>12} {'2% depth':>14} {'4.38% depth':>14}")
    for venue, books in d['cex'].items():
        for p, b in books.items():
            print(f"{venue:9} {p:9} {b['mid']:12.4f} {b['bid_depth_usd']['2']:14,.0f} {b['bid_depth_usd']['4.38']:14,.0f}")
    for a, x in d['dex'].items():
        caps = '  '.join(f"{p}%: {c['usd']:,.0f}{'*' if c['saturated'] else ''}" for p, c in x['capacity_usd_at_slippage'].items())
        print(f"dex       {a:9} capacity at slippage  {caps}  (* = largest size still fits, floor)")
    assert 5e6 < d['cex']['coinbase']['BTC-USD']['bid_depth_usd']['2'] < 5e8
    assert any(q['10'] and q['10']['slippage'] < 0.05 for q in d['dex']['cbBTC']['pools'].values())
    assert all(isinstance(c['saturated'], bool) and c['usd'] > 0 for x in d['dex'].values() for c in x['capacity_usd_at_slippage'].values())
    print('ok')
