"""Live liquidity snapshot: Coinbase L2 + Kraken books, Uniswap/Aerodrome quotes on Base -> data/depth.json."""
import json, os, subprocess, time, datetime as dt, urllib.request
from spine.api import coinbase_get, BASE_RPC, UA

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'depth.json')
CAST = os.path.expanduser('~/.config/.foundry/bin/cast')
PRODUCTS = ['BTC-USD', 'ETH-USD', 'SOL-USD', 'XRP-USD', 'DOGE-USD', 'ADA-USD', 'LTC-USD']
KRAKEN = {'BTC-USD': 'XBTUSD', 'ETH-USD': 'ETHUSD'}
PCTS = [0.5, 1, 2, 3, 4.38, 5, 7.5, 10]
CAP_PCTS = [1, 2, 3, 4.38]

USDC = '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913'
UNIV3_QUOTER = '0x3d4e44Eb1374240CE5F1B871ab261CD16335B76a'
AERO_QUOTER = '0x254cF9E1E6e233aa1AC962CB9B05b2cfeAaE15b0'
UNIV3_SIG = 'quoteExactInputSingle((address,address,uint256,uint24,uint160))(uint256,uint160,uint32,uint256)'
AERO_SIG = 'quoteExactInputSingle((address,address,uint256,int24,uint160))(uint256,uint160,uint32,uint256)'
# name -> (quoter, sig, fee-or-tickSpacing)
POOLS = {'univ3_500': (UNIV3_QUOTER, UNIV3_SIG, 500), 'univ3_3000': (UNIV3_QUOTER, UNIV3_SIG, 3000),
         'aero_100': (AERO_QUOTER, AERO_SIG, 100), 'aero_2000': (AERO_QUOTER, AERO_SIG, 2000)}
DEX_ASSETS = {
    'cbBTC': dict(addr='0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf', decimals=8, cb_product='BTC-USD',
                  sizes=[0.5, 1, 2, 5, 10, 20, 50, 100]),
    'WETH': dict(addr='0x4200000000000000000000000000000000000006', decimals=18, cb_product='ETH-USD',
                 sizes=[10, 50, 100, 250, 500, 1000]),
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


def quote(quoter, sig, token_in, amount_raw, fee, retries=3):
    """USDC out (raw units) or None on revert (pool missing or too shallow). Transient RPC errors are retried."""
    for i in range(retries):
        r = subprocess.run([CAST, 'call', '--rpc-url', BASE_RPC, quoter, sig, f'({token_in},{USDC},{amount_raw},{fee},0)'],
                           capture_output=True, text=True, timeout=60)
        if r.returncode == 0 and r.stdout.strip():
            return int(r.stdout.split()[0])
        if 'revert' in r.stderr.lower():
            return None
        time.sleep(1.5 ** i)
    return None


def dex_asset(asset, mid):
    a = DEX_ASSETS[asset]
    pools = {}
    for name, (quoter, sig, fee) in POOLS.items():
        pools[name] = {}
        for size in a['sizes']:
            raw = quote(quoter, sig, a['addr'], int(size * 10 ** a['decimals']), fee)
            if raw is None:
                pools[name][str(size)] = None
                continue
            out = raw / 1e6
            pools[name][str(size)] = dict(out_usd=out, slippage=1 - out / (size * mid))
    cap = {}
    for s in CAP_PCTS:
        cap[str(s)] = sum(max([float(k) * mid for k, q in pq.items() if q and q['slippage'] <= s / 100], default=0) for pq in pools.values())
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
        print(f"dex       {a:9} {'':12} {'':14} {x['capacity_usd_at_slippage']['4.38']:14,.0f}  (capacity at 4.38% slippage)")
    assert 5e6 < d['cex']['coinbase']['BTC-USD']['bid_depth_usd']['2'] < 5e8
    assert any(q['10'] and q['10']['slippage'] < 0.05 for q in d['dex']['cbBTC']['pools'].values())
    print('ok')
