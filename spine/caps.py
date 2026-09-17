"""Origination caps per market (PLAN.md §4 haircut rule) -> data/caps.json. stdlib only.
Cap = LLTV * (1 - p95 7-day drawdown) from data/prices/daily_*.json, cross-checked against RiskDAO SmartLTV."""
import math, statistics, datetime as dt
from spine.api import MARKETS, lif, load, save, day_ts

GRID = [0.86, 0.80, 0.77, 0.70, 0.625]
SMARTLTV_C = {1.17: 'Jan 2020', 2.58: 'Feb 2021', 5.99: 'Mar 2020'}  # research/sources_prior_art.md
MAX_DRAW = {'BTC': 0.75, 'ETH': 0.75}  # current Coinbase max draw; alts 0.55
DAY = 86400


def dd7(rows):
    """[(ts, drawdown)] per day: close to the min low over the following 7 daily rows, skipping gaps."""
    return [(r[0], max(0.0, 1 - min(x[3] for x in rows[i + 1:i + 8]) / r[4]))
            for i, r in enumerate(rows[:-7]) if rows[i + 7][0] - r[0] == 7 * DAY]


def pct(vals, p):
    return statistics.quantiles(vals, n=100, method='inclusive')[p - 1]


def sigma_annual(rows):
    """Annualized stdev of daily log returns over the trailing 365 days."""
    r = [x for x in rows if x[0] >= rows[-1][0] - 365 * DAY]
    return statistics.stdev(math.log(b[4] / a[4]) for a, b in zip(r, r[1:])) * math.sqrt(365)


def nearest(d, x):
    return min(d, key=lambda k: abs(float(k) - x))


def liquidity(name, product, beta, depth):
    """USD bids within slippage beta: Coinbase + Kraken (nearest measured point) + DEX capacity where present."""
    tot = 0.0
    for venue in depth['cex'].values():
        b = venue.get(product, {}).get('bid_depth_usd')
        if b:
            tot += b[nearest(b, beta * 100)]
    cap = depth['dex'].get(name, {}).get('capacity_usd_at_slippage')
    if cap:
        tot += cap[nearest(cap, beta * 100)]['usd']
    return tot


def market_caps(name, m, depth, summary):
    rows = load('prices/daily_' + m['cb_product'])
    if not rows:
        return None
    d = dd7(rows)
    d23 = [x for _, x in d if _ >= day_ts('2023-01-01')]
    p95, p99 = pct([x for _, x in d], 95), pct([x for _, x in d], 99)
    beta = lif(m['lltv']) - 1
    l, b = liquidity(name, m['cb_product'], beta, depth), summary['markets'][name]['state']['borrow_usd']
    s = sigma_annual(rows)
    grid = sorted({m['lltv'], *GRID}, reverse=True)
    return dict(feed=m['feed'], lltv=m['lltv'], lif=1 + beta,
                dd7_p95_2020=p95, dd7_p99_2020=p99, dd7_p95_2023=pct(d23, 95), dd7_p99_2023=pct(d23, 99),
                cap_p95={str(g): g * (1 - p95) for g in grid}, cap_p99={str(g): g * (1 - p99) for g in grid},
                sigma_annual=s, liquidity_usd=l, borrow_usd=b,
                smartltv={str(c): math.exp(-c * s / math.sqrt(l / b)) - beta for c in SMARTLTV_C})


def build():
    depth, summary = load('depth'), load('summary')
    out = {n: market_caps(n, m, depth, summary) for n, m in MARKETS.items()}
    return dict(generated_at=dt.datetime.now(dt.timezone.utc).isoformat(), markets={n: v for n, v in out.items() if v})


def tables(caps):
    f = lambda x: f'{x * 100:.1f}%'
    print('| Market | Feed | dd7 p95 / p99 since 2020 | dd7 p95 / p99 since 2023 | LLTV | Max draw today | Cap p95 | Cap p99 |')
    print('|---|---|---|---|---|---|---|---|')
    for n, v in caps['markets'].items():
        k = str(v['lltv'])
        print(f"| {n} | {v['feed']} | {f(v['dd7_p95_2020'])} / {f(v['dd7_p99_2020'])} | {f(v['dd7_p95_2023'])} / {f(v['dd7_p99_2023'])} "
              f"| {f(v['lltv'])} | {f(MAX_DRAW.get(v['feed'], 0.55))} | {f(v['cap_p95'][k])} | {f(v['cap_p99'][k])} |")
    print()
    print('Cap = LLTV * (1 - dd7_p95 since 2020) across the backtest grid:')
    print('| Market | ' + ' | '.join(f'LLTV {f(g)}' for g in GRID) + ' |')
    print('|---|' + '---|' * len(GRID))
    for n, v in caps['markets'].items():
        print(f'| {n} | ' + ' | '.join(f(v['cap_p95'][str(g)]) for g in GRID) + ' |')
    print()
    cs = list(SMARTLTV_C)
    print('SmartLTV = exp(-c * sigma / sqrt(l / d)) - beta, beta = LIF - 1. ' + ', '.join(f'c={c} ({w} drawdown)' for c, w in SMARTLTV_C.items()) + '.')
    print('| Market | LLTV | beta | sigma (ann.) | liquidity l | borrow d | ' + ' | '.join(f'LTV c={c}' for c in cs) + ' |')
    print('|---|---|---|---|---|---|' + '---|' * len(cs))
    for n, v in caps['markets'].items():
        print(f"| {n} | {f(v['lltv'])} | {f(v['lif'] - 1)} | {f(v['sigma_annual'])} | ${v['liquidity_usd'] / 1e6:.1f}M | ${v['borrow_usd'] / 1e6:.1f}M | "
              + ' | '.join(f(v['smartltv'][str(c)]) for c in cs) + ' |')


if __name__ == '__main__':
    caps = build()
    save('caps', caps, indent=1)
    tables(caps)
    b = caps['markets']['cbBTC']
    assert 0.10 < b['dd7_p95_2020'] < 0.30 and 0.55 < b['cap_p95']['0.86'] < 0.80
    assert set(caps['markets']) == set(MARKETS)
    assert all(isinstance(x, float) and math.isfinite(x) for v in caps['markets'].values()
               for x in [v['sigma_annual'], v['liquidity_usd'], v['borrow_usd'], *v['cap_p95'].values(), *v['smartltv'].values()])
    print('ok')
