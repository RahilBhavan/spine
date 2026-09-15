"""Every liquidation per market -> data/liquidations_<mkt>.json.
marketTransactions has no orderBy but returns newest first, so we walk timestamp_lte backwards from
now to the last saved timestamp minus a day, then merge. Run: python3.12 -m spine.fetch_liquidations"""
import json, os, time
from spine.api import graphql, MARKETS, CHAIN

DATA = os.path.join(os.path.dirname(__file__), '..', 'data')
Q = '''query($w:MarketTransactionFilters){
  marketTransactions(first:1000, where:$w){
    pageInfo{countTotal} items{ txHash timestamp blockNumber user{address}
      data{ ... on MarketTransactionLiquidationData { liquidator repaidAssets seizedAssets badDebtAssets } } } } }'''


def page(where):
    time.sleep(0.1)
    r = graphql(Q, {'w': where})['marketTransactions']
    return r['pageInfo']['countTotal'], r['items']


def row(it):
    d = it['data']
    return dict(ts=it['timestamp'], block=it['blockNumber'], tx=it['txHash'], borrower=it['user']['address'],
                liquidator=d['liquidator'], repaid_assets=str(d['repaidAssets']), seized_assets=str(d['seizedAssets']),
                bad_debt_assets=str(d['badDebtAssets']))


def key(r):
    return r['tx'], r['borrower'].lower()


def fetch(mid, since=0):
    """Returns {(tx, borrower): row} for liquidations with ts >= since."""
    where = {'chainId_in': [CHAIN], 'marketUniqueKey_in': [mid], 'type_in': ['Liquidation'], 'timestamp_gte': since}
    seen, hi = {}, None
    while True:
        _, items = page(dict(where, timestamp_lte=hi) if hi else where)
        new = [r for r in map(row, items) if key(r) not in seen]
        seen.update((key(r), r) for r in new)
        if not new:  # a full page can come back as 999, so only "nothing new" is a safe stop
            break
        hi = min(it['timestamp'] for it in items)
    return seen


def fetch_market(name):
    m = MARKETS[name]
    path = os.path.join(DATA, 'liquidations_%s.json' % name)
    old = json.load(open(path))['items'] if os.path.exists(path) else []
    merged = {key(r): r for r in old}
    since = max((r['ts'] for r in old), default=1) - 86400
    merged.update(fetch(m['id'], since))
    items = sorted(merged.values(), key=lambda r: (r['ts'], r['tx']))
    total, _ = page({'chainId_in': [CHAIN], 'marketUniqueKey_in': [m['id']], 'type_in': ['Liquidation']})
    if len(items) != total:
        raise RuntimeError('%s: merged %d liquidations, countTotal %d; not writing' % (name, len(items), total))
    out = dict(fetched_at=int(time.time()), market=name, count=len(items), items=items)
    os.makedirs(DATA, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(out, f)
    return total, out


if __name__ == '__main__':
    bad = 0
    for name in MARKETS:
        total, out = fetch_market(name)
        bad += sum(int(r['bad_debt_assets']) for r in out['items'])
        print('%-8s count=%d countTotal=%d' % (name, out['count'], total))
        assert out['count'] == total, (name, out['count'], total)
    print('bad_debt_assets total %d raw = $%.4f' % (bad, bad / 1e6))
    assert bad < 1_000_000  # not literally 0: 274 dust write-offs (1..4238 raw units) sum to ~$0.07 across all markets
    print('ok')
