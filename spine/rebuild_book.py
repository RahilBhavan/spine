"""Rebuild a market's borrower book as of a UTC date (00:00) from Morpho transaction history
-> data/book_<market>_<date>.json, same schema as positions_<market>.json.
Run: .venv/bin/python -m spine.rebuild_book cbBTC 2026-02-03 [2025-10-09 ...] [--max-seconds N]
Several dates share one walk: the walk starts at the latest date and snapshots the accumulators when
the cursor crosses each earlier one (book(T2) = book(T1) - txs in (T2, T1]). Each invocation stops
after max-seconds, checkpoints to data/cache/, and prints "partial, rerun to continue"."""
import json, os, sys, time, glob, datetime as dt
from spine.api import graphql, MARKETS, CHAIN, lif, DATA, load, save, day_ts, budget, argv_max_seconds, row_ts, row_price

TYPES = ['Borrow', 'Repay', 'SupplyCollateral', 'WithdrawCollateral', 'Liquidation']
Q = '''query($w:MarketTransactionFilters){ marketTransactions(first:1000, where:$w){ items{ txHash timestamp type user{address}
  data{ ... on MarketTransactionTransferData { assets shares } ... on MarketTransactionCollateralTransferData { assets }
        ... on MarketTransactionLiquidationData { repaidAssets repaidShares seizedAssets } } } } }'''
QH = '''{ marketById(marketId:"%s", chainId:%d){ historicalState{
  borrowAssets(options:{startTimestamp:%d,endTimestamp:%d,interval:DAY}){x y}
  borrowShares(options:{startTimestamp:%d,endTimestamp:%d,interval:DAY}){x y}
  borrowAssetsUsd(options:{startTimestamp:%d,endTimestamp:%d,interval:DAY}){x y}
  collateralAssetsUsd(options:{startTimestamp:%d,endTimestamp:%d,interval:DAY}){x y}
  collateralAssets(options:{startTimestamp:%d,endTimestamp:%d,interval:DAY}){x y} } } }'''


def key(it):
    d = it['data']
    return '%s|%s|%s|%s' % (it['txHash'], it['user']['address'].lower(), it['type'], d.get('assets', d.get('repaidAssets')))


def apply(acc, it):
    """acc[user] = [collateral_units, borrow_shares]; Liquidation rows list the borrower as user."""
    u, d, t = it['user']['address'], it['data'], it['type']
    a = acc.setdefault(u, [0, 0])
    if t == 'Borrow':
        a[1] += int(d['shares'])
    elif t == 'Repay':
        a[1] -= int(d['shares'])
    elif t == 'SupplyCollateral':
        a[0] += int(d['assets'])
    elif t == 'WithdrawCollateral':
        a[0] -= int(d['assets'])
    else:
        a[0] -= int(d['seizedAssets'])
        a[1] -= int(d['repaidShares'])


def walk(market, dates, max_seconds):
    """Page marketTransactions newest-first from day_ts(max date) down to genesis. Returns state dict or None if partial."""
    T0 = max(dates, key=day_ts)
    ck = 'cache/book_%s_%s' % (market, T0)
    st = load(ck) or dict(cursor=day_ts(T0), acc={}, snapshots={}, seen=[], pages=0, done=False)
    if st['done']:
        return st
    where = {'chainId_in': [CHAIN], 'marketUniqueKey_in': [MARKETS[market]['id']], 'type_in': TYPES}
    seen, within_budget = set(st['seen']), budget(max_seconds)  # seen: keys at the cursor timestamp only (the next page re-serves them)
    earlier = sorted(((day_ts(d), d) for d in dates if d != T0 and d not in st['snapshots']), reverse=True)
    while True:
        time.sleep(0.2)
        items = graphql(Q, {'w': dict(where, timestamp_lte=st['cursor'])})['marketTransactions']['items']
        new = [it for it in items if key(it) not in seen]
        if not new:
            st['done'] = True
            break
        for it in new:
            while earlier and it['timestamp'] <= earlier[0][0]:
                st['snapshots'][earlier.pop(0)[1]] = {u: list(v) for u, v in st['acc'].items()}
            apply(st['acc'], it)
        lo = min(it['timestamp'] for it in items)
        seen = {key(it) for it in items if it['timestamp'] == lo}
        st['cursor'], st['pages'] = lo, st['pages'] + 1
        if st['pages'] % 50 == 0:
            print('  page %d, cursor %s, users %d' % (st['pages'], dt.datetime.fromtimestamp(lo, dt.timezone.utc).date(), len(st['acc'])), flush=True)
        if st['pages'] % 50 == 0 or not within_budget():
            st['seen'] = sorted(seen)
            save(ck, st)
            if not within_budget():
                print('partial, rerun to continue (%d pages, cursor %s)' % (st['pages'], dt.datetime.fromtimestamp(lo, dt.timezone.utc)))
                return None
    for _, d in earlier:  # dates before the market existed
        st['snapshots'][d] = {u: list(v) for u, v in st['acc'].items()}
    save(ck, st)
    return st


def nearest(rows, T, x):
    """The row whose x(row) is closest to T."""
    return min(rows, key=lambda r: abs(x(r) - T))


def price_at(market, T):
    """Nearest Chainlink update from data/oracle if T falls in a fetched window, else the daily Coinbase close ending at T."""
    for f in glob.glob(os.path.join(DATA, 'oracle', '*_%s.json' % MARKETS[market]['feed'])):
        rows = json.load(open(f))
        if rows and row_ts(rows[0]) <= T <= row_ts(rows[-1]):
            return row_price(nearest(rows, T, row_ts)), os.path.basename(f)
    daily = load('prices/daily_%s' % MARKETS[market]['cb_product'])
    return nearest(daily, T - 86400, lambda c: c[0])[4], 'daily close'  # candle [ts, open, high, low, close]


def build(market, date, acc, snap):
    m, T = MARKETS[market], day_ts(date)
    h = graphql(QH % ((m['id'], CHAIN) + (T - 86400, T + 86400) * 5))['marketById']['historicalState']
    at = lambda series: nearest(h[series], T, lambda d: d['x'])['y']
    ratio = int(at('borrowAssets')) / int(at('borrowShares'))
    price, src = price_at(market, T)
    L, pos = lif(m['lltv']), []
    for u, (c, s) in acc.items():
        s -= snap.get(u, [0, 0])[1]
        c -= snap.get(u, [0, 0])[0]
        if s <= 0:
            continue
        b, cu = s * ratio / 10 ** 6, c / 10 ** m['decimals'] * price
        pos.append(dict(user=u, collateral=str(c), borrow_assets=str(int(s * ratio)), collateral_usd=cu, borrow_usd=b,
                        health_factor=cu * m['lltv'] / b if b else None))
    state = dict(borrowAssetsUsd=at('borrowAssetsUsd'), collateralAssetsUsd=at('collateralAssetsUsd'), collateralAssets=str(at('collateralAssets')))
    out = dict(as_of=T, as_of_date=date, market=market, market_id=m['id'], lltv=m['lltv'], price=price, price_source=src, shares_to_assets=ratio,
               count=len(pos), borrow_usd_total=sum(p['borrow_usd'] for p in pos), collateral_usd_total=sum(p['collateral_usd'] for p in pos),
               market_state=state, positions=pos)
    save('book_%s_%s' % (market, date), out)
    return out


if __name__ == '__main__':
    max_seconds, args, _ = argv_max_seconds()
    market, dates = args[0], args[1:]
    assert market in MARKETS and dates
    st = walk(market, dates, max_seconds)
    if st is None:
        sys.exit(0)
    T0 = max(dates, key=day_ts)
    for d in dates:
        out = build(market, d, st['acc'], {} if d == T0 else st['snapshots'][d])
        ms = out['market_state']
        eb = out['borrow_usd_total'] / ms['borrowAssetsUsd'] - 1
        ec = out['collateral_usd_total'] / ms['collateralAssetsUsd'] - 1
        print('%s %s: %d positions, borrow $%.1fM vs API $%.1fM (%+.2f%%), collateral $%.1fM vs API $%.1fM (%+.2f%%), price %.0f (%s)' % (
            market, d, out['count'], out['borrow_usd_total'] / 1e6, ms['borrowAssetsUsd'] / 1e6, 100 * eb,
            out['collateral_usd_total'] / 1e6, ms['collateralAssetsUsd'] / 1e6, 100 * ec, out['price'], out['price_source']))
        assert abs(eb) < 0.03, eb
        assert abs(ec) < 0.05, ec
    print('complete')
