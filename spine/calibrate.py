"""Replay each stress window from Liquidate events + Chainlink path -> data/calibration.json.
Per window/market: liquidated volume (USD at the oracle price of the liquidation block), realized bonus
(seized/repaid - 1), latency from the oracle crossing the borrower's liquidation price to the Liquidate
event, and liquidator concentration.
Run: python3.12 -m spine.calibrate <window> [--max-seconds N]   one window -> data/cache/calib_<window>.json
     python3.12 -m spine.calibrate                              assemble data/calibration.json, print tables
The latency step fetches one Morpho history per borrower (cached in data/cache/history_*.json); when the
time budget runs out it exits 0 with "partial", rerun until it prints "complete"."""
import bisect, json, os, sys, time, datetime
from spine.api import graphql, rpc, MARKETS, CHAIN
from spine.fetch_oracle import WINDOWS, day_ts

DATA = os.path.join(os.path.dirname(__file__), '..', 'data')
CACHE = os.path.join(DATA, 'cache')
ORACLE = {'cbBTC': 'BTC', 'WETH': 'ETH'}  # market -> Chainlink feed in data/oracle/
LLTV = 0.86
CAP = 1500  # borrowers per window/market for the latency step
LOOKBACK = 86400  # search for the crossing this long before the liquidation
T0 = time.time()
MAX_SECONDS = float(sys.argv[sys.argv.index('--max-seconds') + 1]) if '--max-seconds' in sys.argv else 200
HIST_Q = '''query($w:MarketTransactionFilters){ marketTransactions(first:1000, where:$w){ items {
  type timestamp blockNumber txHash user { address } data {
    ... on MarketTransactionTransferData { assets shares }
    ... on MarketTransactionCollateralTransferData { assets }
    ... on MarketTransactionLiquidationData { repaidAssets repaidShares seizedAssets } } } } }'''
HIST_TYPES = ['Borrow', 'Repay', 'SupplyCollateral', 'WithdrawCollateral', 'Liquidation']


class Budget(Exception):
    pass


def check_budget():
    if time.time() - T0 > MAX_SECONDS:
        raise Budget()


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p * (len(xs) - 1))))] if xs else None


def day(ts):
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime('%Y-%m-%d')


class Oracle:
    """Sorted [[ts, block, price]] with lookups by block (state at a block) and by time (crossing search)."""
    def __init__(self, window, asset):
        self.rows = json.load(open(os.path.join(DATA, 'oracle', '%s_%s.json' % (window, asset))))
        self.blocks = [r[1] for r in self.rows]
        self.ts = [r[0] for r in self.rows]

    def price_at(self, block):
        i = bisect.bisect_right(self.blocks, block) - 1
        assert i >= 0, block
        return self.rows[i][2]

    def crossings(self, block, ts, p_star):
        """(first update below p_star, last downward crossing below p_star) within [ts - LOOKBACK, block],
        or a string saying why there is none. First = time since first eligible; last = bot reaction time."""
        i0, i1 = bisect.bisect_left(self.ts, ts - LOOKBACK), bisect.bisect_right(self.blocks, block)
        if i0 >= i1:
            return 'no_updates'
        if self.rows[i0][2] < p_star:
            return 'crossed_before_window'
        first = last = None
        for j in range(i0, i1):
            if self.rows[j][2] < p_star:
                first = first or self.rows[j]
                if self.rows[j - 1][2] >= p_star:
                    last = self.rows[j]
        return (first, last) if first else 'never_crossed'


def liquidations(market, window):
    a, b = WINDOWS[window]
    t0, t1 = day_ts(a), day_ts(b) + 86400
    rows = [r for r in json.load(open(os.path.join(DATA, 'liquidations_%s.json' % market)))['items'] if t0 <= r['ts'] < t1]
    return sorted(rows, key=lambda r: (r['ts'], r['tx']))


def price_rows(rows, oracle, decimals):
    for r in rows:
        p = oracle.price_at(r['block'])
        r['price'] = p
        r['repaid_usd'] = int(r['repaid_assets']) / 1e6
        r['seized_usd'] = int(r['seized_assets']) / 10 ** decimals * p
        r['bad_debt_usd'] = int(r['bad_debt_assets']) / 1e6
    return rows


def volume(rows):
    daily, b5, b60 = {}, {}, {}
    for r in rows:
        d = daily.setdefault(day(r['ts']), dict(n=0, repaid_usd=0, seized_usd=0, bad_debt_usd=0))
        d['n'] += 1
        for k in ('repaid_usd', 'seized_usd', 'bad_debt_usd'):
            d[k] += r[k]
        b5[r['ts'] // 300] = b5.get(r['ts'] // 300, 0) + r['repaid_usd']
        b60[r['ts'] // 3600] = b60.get(r['ts'] // 3600, 0) + r['repaid_usd']

    def peak(b, w):
        k = max(b, key=b.get)
        return dict(repaid_usd=b[k], start=datetime.datetime.fromtimestamp(k * w, datetime.timezone.utc).isoformat())
    vol = dict(n=len(rows), borrowers=len({r['borrower'].lower() for r in rows}),
               repaid_usd=sum(r['repaid_usd'] for r in rows), seized_usd=sum(r['seized_usd'] for r in rows),
               bad_debt_usd=sum(r['bad_debt_usd'] for r in rows))
    return vol, dict(sorted(daily.items())), dict(peak_5m=peak(b5, 300), peak_1h=peak(b60, 3600))


def bonus(rows):
    xs = [r['seized_usd'] / r['repaid_usd'] - 1 for r in rows if r['repaid_usd'] > 0]
    return dict(n=len(xs), p10=pct(xs, .1), p50=pct(xs, .5), p90=pct(xs, .9), expected=1 / (0.3 * LLTV + 0.7) - 1)


def hist_path(market, addr):
    return os.path.join(CACHE, 'history_%s_%s.json' % (market, addr.lower()))


def cached(market, addr, upto):
    """Borrower's cached Morpho events in this market with timestamp <= upto, or None if not fetched that far."""
    if os.path.exists(hist_path(market, addr)):
        c = json.load(open(hist_path(market, addr)))
        if c['upto'] >= upto:
            return [x for x in c['items'] if x['timestamp'] <= upto]


def save(market, addr, upto, items):
    with open(hist_path(market, addr), 'w') as f:
        json.dump(dict(upto=upto, items=sorted(items, key=lambda x: (x['blockNumber'], x['timestamp']))), f)


def fetch_page(market, addrs, upto):
    time.sleep(0.09)
    where = {'chainId_in': [CHAIN], 'marketUniqueKey_in': [MARKETS[market]['id']], 'userAddress_in': addrs,
             'timestamp_lte': upto, 'type_in': HIST_TYPES}
    return graphql(HIST_Q, {'w': where})['marketTransactions']['items']


def fetch_histories(market, need, batch=10):
    """need: {addr: upto}. Queries `batch` users at once (newest first) and pages back on timestamp_lte
    until a short page, like fetch_liquidations does; then splits the events per user and caches them."""
    need = sorted(need.items())
    for i in range(0, len(need), batch):
        check_budget()
        chunk = need[i:i + batch]
        addrs, upto = [a for a, _ in chunk], max(u for _, u in chunk)
        items, hi = {}, upto
        while True:
            page = fetch_page(market, addrs, hi)
            new = {json.dumps(x, sort_keys=True): x for x in page if json.dumps(x, sort_keys=True) not in items}
            items.update(new)
            if len(page) < 1000 or not new:
                break
            hi = min(x['timestamp'] for x in page)
        by = {a.lower(): [] for a in addrs}
        for x in items.values():
            by[x['user']['address'].lower()].append(x)
        for a in addrs:
            save(market, a, upto, by[a.lower()])


def latency_one(r, h, oracle, decimals):
    """Returns dict(first, last, full) latencies in seconds, or a string reason for exclusion."""
    this = [x for x in h if x['txHash'] == r['tx'] and x['type'] == 'Liquidation']
    if not this:
        return 'not_in_history'
    earlier = [x for x in h if x['blockNumber'] < r['block'] or (x['blockNumber'] == r['block'] and x['txHash'] != r['tx'])]
    s = lambda t, k: sum(int(x['data'][k]) for x in earlier if x['type'] == t)
    coll = s('SupplyCollateral', 'assets') - s('WithdrawCollateral', 'assets') - s('Liquidation', 'seizedAssets')
    shares = s('Borrow', 'shares') - s('Repay', 'shares') - s('Liquidation', 'repaidShares')
    repaid_shares = int(this[0]['data']['repaidShares'])
    if coll <= 0 or shares <= 0 or repaid_shares <= 0:
        return 'inconsistent_history'
    full = repaid_shares == shares
    debt = int(r['repaid_assets']) / 1e6 * (1 if full else shares / repaid_shares)
    p_star = debt / (coll / 10 ** decimals * LLTV)
    c = oracle.crossings(r['block'], r['ts'], p_star)
    if isinstance(c, str):
        return c
    return dict(first=r['ts'] - c[0][0], last=r['ts'] - c[1][0], full=full)


def latency(market, rows, oracle, decimals):
    if len(rows) > CAP:
        rows = [rows[i * len(rows) // CAP] for i in range(CAP)]
    need = {}
    for r in rows:
        if cached(market, r['borrower'], r['ts']) is None:
            need[r['borrower']] = max(need.get(r['borrower'], 0), r['ts'])
    fetch_histories(market, need)
    ok, excluded, full = [], {}, 0
    for r in rows:
        res = latency_one(r, cached(market, r['borrower'], r['ts']), oracle, decimals)
        if isinstance(res, str):
            excluded[res] = excluded.get(res, 0) + 1
            continue
        ok.append(res)
        full += res['full']
    n = len(ok)

    def stats(k):
        xs = [x[k] for x in ok]
        return dict(sampled=len(rows), n=n, excluded=excluded, full_share=full / n if n else None,
                    p50=pct(xs, .5), p90=pct(xs, .9), p99=pct(xs, .99),
                    within={str(s): sum(x <= s for x in xs) / n if n else None for s in (2, 60, 300, 1800)})
    return stats('last'), stats('first')


def liquidators(rows):
    by = {}
    for r in rows:
        d = by.setdefault(r['liquidator'].lower(), dict(address=r['liquidator'], repaid_usd=0, count=0))
        d['repaid_usd'] += r['repaid_usd']
        d['count'] += 1
    total = sum(d['repaid_usd'] for d in by.values())
    top = sorted(by.values(), key=lambda d: -d['repaid_usd'])[:10]
    for d in top:
        d['share'] = d['repaid_usd'] / total if total else None
        time.sleep(0.25)
        d['is_contract'] = rpc('eth_getCode', [d['address'], 'latest']) != '0x'
    return dict(distinct=len(by), top=top)


def run_window(window):
    os.makedirs(CACHE, exist_ok=True)
    out = {}
    for market, asset in ORACLE.items():
        dec = MARKETS[market]['decimals']
        oracle = Oracle(window, asset)
        rows = price_rows(liquidations(market, window), oracle, dec)
        if not rows:
            out[market] = None
            continue
        vol, daily, peaks = volume(rows)
        lat, lat_first = latency(market, rows, oracle, dec)
        out[market] = dict(volume=vol, daily=daily, peaks=peaks, bonus=bonus(rows), latency=lat,
                           latency_first_eligible=lat_first, liquidators=liquidators(rows))
        print('%s %-5s n=%d repaid=$%.1fM bonus_p50=%.4f latency n=%d p50=%s excluded=%s' % (
            window, market, vol['n'], vol['repaid_usd'] / 1e6, out[market]['bonus']['p50'], lat['n'], lat['p50'], lat['excluded']))
    with open(os.path.join(CACHE, 'calib_%s.json' % window), 'w') as f:
        json.dump(out, f)


def assemble():
    wins = {w: json.load(open(os.path.join(CACHE, 'calib_%s.json' % w))) for w in WINDOWS}
    pc = lambda x: '%.2f%%' % (100 * x) if x is not None else '-'
    for w, ms in wins.items():
        print('\n%s  (%s..%s)' % (w, *WINDOWS[w]))
        print('%-6s %5s %11s %11s %8s %8s %8s %9s %9s %7s %8s %6s' % (
            'market', 'n', 'repaid_usd', 'seized_usd', 'bonus50', 'last_p50', 'last_p90', 'first_p50', 'first_p90', 'w/in60', 'top_liq', 'full'))
        for m, r in ms.items():
            if not r:
                print('%-6s %5d' % (m, 0))
                continue
            v, l, lf, t = r['volume'], r['latency'], r['latency_first_eligible'], r['liquidators']['top'][0]
            print('%-6s %5d %11s %11s %8s %8s %8s %9s %9s %7s %8s %6s' % (
                m, v['n'], '$%.2fM' % (v['repaid_usd'] / 1e6), '$%.2fM' % (v['seized_usd'] / 1e6), pc(r['bonus']['p50']),
                l['p50'], l['p90'], lf['p50'], lf['p90'], pc(l['within']['60']), pc(t['share']), pc(l['full_share'])))
    feb = wins['Feb2026']['cbBTC']['daily']['2026-02-05']['seized_usd']
    assert abs(feb / 90.7e6 - 1) < 0.30, feb
    for w, ms in wins.items():
        assert abs(ms['cbBTC']['bonus']['p50'] - 0.0438) < 0.005, (w, ms['cbBTC']['bonus']['p50'])
    for w in ('Feb2026', 'Jun2026a'):
        assert wins[w]['cbBTC']['latency']['n'] >= 100, (w, wins[w]['cbBTC']['latency']['n'])
    out = dict(generated_at=int(time.time()), windows=wins)
    with open(os.path.join(DATA, 'calibration.json'), 'w') as f:
        json.dump(out, f, indent=1)
    print('\nok: data/calibration.json')


if __name__ == '__main__':
    args = sys.argv[1:]
    if '--max-seconds' in args:
        del args[args.index('--max-seconds'):args.index('--max-seconds') + 2]
    if args:
        try:
            run_window(args[0])
            print('complete')
        except Budget:
            print('partial (%s), rerun to continue' % args[0])
    else:
        assemble()
