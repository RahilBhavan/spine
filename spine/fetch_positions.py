"""Every Morpho position with debt, per market -> data/positions_<mkt>.json.
The API caps first=1000 and skip=10000, so we walk healthFactor ascending, moving healthFactor_gte
to the last value seen. Run from repo root: python3.12 -m spine.fetch_positions"""
import time
from spine.api import graphql, MARKETS, CHAIN, save

Q = '''query($s:Int,$o:MarketPositionOrderBy,$w:MarketPositionFilters){
  marketPositions(first:1000, skip:$s, orderBy:$o, orderDirection:Asc, where:$w){
    pageInfo{countTotal} items{ user{address} healthFactor state{collateral borrowAssets borrowAssetsUsd collateralUsd} } } }'''
QS = '{ marketById(marketId:"%s", chainId:%d){ state{ borrowAssetsUsd collateralAssetsUsd supplyAssetsUsd utilization borrowApy } } }'


def page(where, order='HealthFactor', skip=0):
    time.sleep(0.1)  # 750 req/min
    r = graphql(Q, {'s': skip, 'o': order, 'w': where})['marketPositions']
    return r['pageInfo']['countTotal'], r['items']


def row(it):
    s = it['state']
    return dict(user=it['user']['address'], collateral=str(s['collateral']), borrow_assets=str(s['borrowAssets']),
                collateral_usd=s['collateralUsd'], borrow_usd=s['borrowAssetsUsd'], health_factor=it['healthFactor'])


def walk(where):
    """Dust positions (borrowShares>=1, borrowAssets 0) have a null healthFactor that the
    healthFactor_gte filter drops; they sort first under BorrowShares Asc."""
    seen, skip = {}, 0
    while True:  # ponytail: skip caps at 10000; >10k dust positions in one market would need a cursor
        _, items = page(where, 'BorrowShares', skip)
        seen.update((it['user']['address'].lower(), it) for it in items if it['healthFactor'] is None)
        if not items or any(it['healthFactor'] is not None for it in items):
            break
        skip += 1000
    lo = 0
    while True:
        _, items = page(dict(where, healthFactor_gte=lo))
        new = [it for it in items if it['user']['address'].lower() not in seen]
        seen.update((it['user']['address'].lower(), it) for it in new)
        if len(items) < 1000 or not new:  # ponytail: >1000 positions at one exact HF would stall; dedupe guard breaks instead
            break
        lo = items[-1]['healthFactor']
    return seen


def fetch(mid):
    """Returns (countTotal, positions). The book is live; a borrow landing mid-walk behind the cursor
    makes count != countTotal, so re-walk (up to 3 times) until they agree, else raise before anything is written."""
    where = {'chainId_in': [CHAIN], 'marketUniqueKey_in': [mid], 'borrowShares_gte': 1}
    for _ in range(3):
        seen = walk(where)
        total, _ = page(where)  # unbanded count, taken right after the walk
        if len(seen) == total:
            return total, [row(it) for it in seen.values()]
    raise RuntimeError('%s: walked %d positions, countTotal %d after 3 walks' % (mid, len(seen), total))


def fetch_market(name):
    m = MARKETS[name]
    total, pos = fetch(m['id'])
    state = graphql(QS % (m['id'], CHAIN))['marketById']['state']
    out = dict(fetched_at=int(time.time()), market=name, market_id=m['id'], lltv=m['lltv'], count=len(pos),
               borrow_usd_total=sum(p['borrow_usd'] for p in pos), collateral_usd_total=sum(p['collateral_usd'] for p in pos),
               market_state=state, positions=pos)
    save('positions_%s' % name, out)
    return total, out


if __name__ == '__main__':
    for name in MARKETS:
        total, out = fetch_market(name)
        users = [p['user'].lower() for p in out['positions']]
        book = out['market_state']['borrowAssetsUsd']
        print('%-8s count=%d countTotal=%d borrow_usd=%.0f market=%.0f' % (name, out['count'], total, out['borrow_usd_total'], book))
        assert out['count'] == total, (name, out['count'], total)
        assert len(users) == len(set(users)), name
        if book > 1e5:  # dust markets round badly
            assert abs(out['borrow_usd_total'] - book) <= 0.01 * book, (name, out['borrow_usd_total'], book)
    print('ok')
