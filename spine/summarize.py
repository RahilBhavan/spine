"""Aggregate data/*.json into data/summary.json so the site never loads the raw positions files.
Run: .venv/bin/python -m spine.summarize"""
import sys, datetime, collections
from spine.api import MARKETS, lif, load, save

BIN = 0.02
DROPS = [round(d * 0.01, 2) for d in range(0, 71)]
CAPACITY_K = dict(dex=0.5, cex=0.3)  # stress multipliers on today's depth at 4.38%; same defaults as backtest k_dex / k_cex
HF_STEPS = [round(1 + 2 * i / 39, 4) for i in range(40)]


def is_cb(wallets, user):
    return wallets.get(user.lower()) in ('v1.0', 'v1.1')


def ltv_hist(pos):
    bins = [dict(lo=round(i * BIN, 2), count=0, borrow_usd=0.0, collateral_usd=0.0, cb_count=0, cb_borrow_usd=0.0, cb_collateral_usd=0.0)
            for i in range(int(1 / BIN))]
    for p in pos:
        b = bins[min(int(p['ltv'] / BIN), len(bins) - 1)]
        b['count'] += 1
        b['borrow_usd'] += p['borrow_usd']
        b['collateral_usd'] += p['collateral_usd']
        if p['is_coinbase']:
            b['cb_count'] += 1
            b['cb_borrow_usd'] += p['borrow_usd']
            b['cb_collateral_usd'] += p['collateral_usd']
    return bins


def liquidatable_curve(pos, lltv, bad_ltv):
    out = []
    for d in DROPS:
        row = dict(drop=d, borrow_usd=0.0, collateral_usd=0.0, count=0, bad_borrow_usd=0.0, bad_collateral_usd=0.0, bad_count=0,
                   cb_borrow_usd=0.0, cb_collateral_usd=0.0, cb_count=0, cb_bad_borrow_usd=0.0, cb_bad_collateral_usd=0.0, cb_bad_count=0)
        for p in pos:
            ltv = p['ltv'] / (1 - d)
            if ltv <= lltv:
                continue
            for pre in (('',) + (('cb_',) if p['is_coinbase'] else ())):
                row[pre + 'borrow_usd'] += p['borrow_usd']
                row[pre + 'collateral_usd'] += p['collateral_usd']
                row[pre + 'count'] += 1
                if ltv > bad_ltv:
                    row[pre + 'bad_borrow_usd'] += p['borrow_usd']
                    row[pre + 'bad_collateral_usd'] += p['collateral_usd']
                    row[pre + 'bad_count'] += 1
        out.append(row)
    return out


def capacity_ab(depth):
    """Modeled AB liquidator capacity: stressed DEX capacity plus stressed Coinbase bids, both at the 4.38% bonus."""
    dex = depth.get('dex_capacity_usd', {}).get('4.38', 0.0)
    cex = depth.get('coinbase', {}).get('bid_depth_usd', {}).get('4.38', 0.0)
    return CAPACITY_K['dex'] * dex + CAPACITY_K['cex'] * cex


def distance_to_capacity(curve, cap):
    """Smallest price drop at which liquidatable borrow exceeds cap; None if it never does within DROPS."""
    return next((c['drop'] for c in curve if c['borrow_usd'] > cap), None) if cap else None


def hf_cdf(pos):
    total = sum(p['borrow_usd'] for p in pos) or 1
    return [dict(hf=h, share=sum(p['borrow_usd'] for p in pos if p['health_factor'] is not None and p['health_factor'] < h) / total) for h in HF_STEPS]


def liquidations(name, decimals):
    raw = load(f'liquidations_{name}')
    if not raw:
        return [], []
    daily, by_liq = collections.defaultdict(lambda: dict(n=0, repaid_usd=0.0, seized_units=0.0, bad_debt_usd=0.0)), collections.defaultdict(lambda: [0, 0.0])
    for it in raw['items']:
        day = datetime.datetime.fromtimestamp(it['ts'], datetime.UTC).strftime('%Y-%m-%d')
        d, repaid = daily[day], int(it['repaid_assets']) / 1e6
        d['n'] += 1
        d['repaid_usd'] += repaid
        d['seized_units'] += int(it['seized_assets']) / 10 ** decimals
        d['bad_debt_usd'] += int(it['bad_debt_assets']) / 1e6
        by_liq[it['liquidator']][0] += 1
        by_liq[it['liquidator']][1] += repaid
    total = sum(v[1] for v in by_liq.values()) or 1
    top = sorted(by_liq.items(), key=lambda kv: -kv[1][1])[:10]
    return ([dict(day=k, **v) for k, v in sorted(daily.items())],
            [dict(liquidator=a, count=n, repaid_usd=r, share=r / total) for a, (n, r) in top])


def depth_for(depth, name, product):
    if not depth:
        return {}
    out = {}
    for venue in ('coinbase', 'kraken'):
        v = depth['cex'].get(venue, {}).get(product)
        if v:
            out[venue] = dict(mid=v['mid'], bid_depth_usd=v['bid_depth_usd'])
    if name in depth.get('dex', {}):
        cap = depth['dex'][name]['capacity_usd_at_slippage']  # {pct: {usd, saturated}}; keep the flat shape site/app.js reads
        out['dex_capacity_usd'] = {k: v['usd'] for k, v in cap.items()}
        out['dex_capacity_saturated'] = {k: v['saturated'] for k, v in cap.items()}
    return out


def summarize_market(name, m, wallets, depth):
    raw = load(f'positions_{name}')
    if not raw:
        return None
    pos = [dict(user=p['user'], borrow_usd=p['borrow_usd'], collateral_usd=p['collateral_usd'], health_factor=p['health_factor'],
                ltv=p['borrow_usd'] / p['collateral_usd'] if p['collateral_usd'] else 1.0, is_coinbase=is_cb(wallets, p['user']))
           for p in raw['positions'] if p['borrow_assets'] != '0']
    units = sum(int(p['collateral']) for p in raw['positions']) / 10 ** m['decimals']
    coll_usd = sum(p['collateral_usd'] for p in raw['positions'])
    ms, L = raw['market_state'], lif(m['lltv'])
    borrow, cb_borrow = sum(p['borrow_usd'] for p in pos), sum(p['borrow_usd'] for p in pos if p['is_coinbase'])
    state = dict(borrow_usd=ms['borrowAssetsUsd'], collateral_usd=ms['collateralAssetsUsd'], supply_usd=ms['supplyAssetsUsd'],
                 utilization=ms['utilization'], borrow_apy=ms['borrowApy'], lltv=m['lltv'], lif=L, bad_debt_ltv=1 / L,
                 price=coll_usd / units if units else None, n_positions=len(pos),
                 coinbase_share_count=sum(p['is_coinbase'] for p in pos) / len(pos) if pos else 0,
                 coinbase_share_borrow=cb_borrow / borrow if borrow else 0)
    top = sorted(pos, key=lambda p: -p['borrow_usd'])[:25]
    daily, liqs = liquidations(name, m['decimals'])
    curve, dep = liquidatable_curve(pos, m['lltv'], 1 / L), depth_for(depth, name, m['cb_product'])
    state['capacity_ab_usd'] = capacity_ab(dep)
    state['distance_to_capacity'] = distance_to_capacity(curve, state['capacity_ab_usd'])
    return dict(state=state, ltv_hist=ltv_hist(pos), liquidatable_curve=curve, hf_cdf=hf_cdf(pos),
                top_borrowers=top, liquidations_daily=daily, liquidators_top=liqs, depth=dep)


def build():
    wallets, depth = load('coinbase_wallets') or {}, load('depth')
    markets = {n: s for n, m in MARKETS.items() if (s := summarize_market(n, m, wallets, depth))}
    borrow = sum(s['state']['borrow_usd'] for s in markets.values())
    totals = dict(borrow_usd=borrow, collateral_usd=sum(s['state']['collateral_usd'] for s in markets.values()),
                  n_positions=sum(s['state']['n_positions'] for s in markets.values()),
                  coinbase_share_borrow=sum(s['state']['borrow_usd'] * s['state']['coinbase_share_borrow'] for s in markets.values()) / borrow if borrow else 0)
    return dict(generated_at=datetime.datetime.now(datetime.UTC).isoformat(timespec='seconds'), markets=markets, totals=totals)


if __name__ == '__main__':
    check = '--check' in sys.argv  # level asserts only; the cron runs without it
    out = build()
    save('summary', out, separators=(',', ':'))
    m = out['markets']['cbBTC']
    st, curve = m['state'], {c['drop']: c for c in m['liquidatable_curve']}
    hist_sum = sum(b['borrow_usd'] for b in m['ltv_hist'])
    assert abs(hist_sum - st['borrow_usd']) / st['borrow_usd'] < 0.005, (hist_sum, st['borrow_usd'])
    above = sum(b['borrow_usd'] for b in m['ltv_hist'] if b['lo'] >= st['lltv'] - 1e-9)
    assert curve[0.0]['borrow_usd'] <= above + 1, (curve[0.0]['borrow_usd'], above)
    if check:
        assert 150e6 < curve[0.3]['borrow_usd'] < 500e6, curve[0.3]['borrow_usd']
    print('markets: %d, total borrow $%.0fM, positions %d, coinbase share %.1f%%' % (
        len(out['markets']), out['totals']['borrow_usd'] / 1e6, out['totals']['n_positions'], 100 * out['totals']['coinbase_share_borrow']))
    print('cbBTC borrow $%.0fM, price $%.0f, n=%d, cb share %.1f%%' % (st['borrow_usd'] / 1e6, st['price'], st['n_positions'], 100 * st['coinbase_share_borrow']))
    print('cbBTC liquidatable at 0/-10/-20/-30%%: $%.1fM / $%.1fM / $%.1fM / $%.1fM' % tuple(curve[d]['borrow_usd'] / 1e6 for d in (0.0, 0.1, 0.2, 0.3)))
    print('cbBTC bad-debt zone at -30%%: $%.1fM' % (curve[0.3]['bad_borrow_usd'] / 1e6))
    print('cbBTC capacity at 4.38%%: dex $%.1fM, coinbase $%.1fM' % (m['depth']['dex_capacity_usd']['4.38'] / 1e6, m['depth']['coinbase']['bid_depth_usd']['4.38'] / 1e6))
    assert m['hf_cdf'][0]['share'] == 0 and 0 < m['hf_cdf'][-1]['share'] <= 1 and len(m['hf_cdf']) == 40
    assert st['distance_to_capacity'] is None or curve[st['distance_to_capacity']]['borrow_usd'] > st['capacity_ab_usd'] >= curve[round(max(0.0, st['distance_to_capacity'] - 0.01), 2)]['borrow_usd']
    print('distance to AB capacity: ' + ', '.join('%s %s (cap $%.1fM)' % (n, 'none' if s['state']['distance_to_capacity'] is None else '-%.0f%%' % (100 * s['state']['distance_to_capacity']), s['state']['capacity_ab_usd'] / 1e6)
                                                for n, s in out['markets'].items()))
