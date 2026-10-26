"""Every Morpho position with debt, per market -> data/positions_<mkt>.json.
The API caps first=1000 and skip=10000, so we walk borrowShares ascending, moving borrowShares_gte
to the last value seen. Run from repo root: .venv/bin/python -m spine.fetch_positions"""
import time
from spine.api import graphql, MARKETS, CHAIN, save

Q = '''query($w:MarketPositionFilters){
  marketPositions(first:1000, orderBy:BorrowShares, orderDirection:Asc, where:$w){
    pageInfo{countTotal} items{ user{address} healthFactor state{collateral borrowShares borrowAssets borrowAssetsUsd collateralUsd} } } }'''
QS = '{ marketById(marketId:"%s", chainId:%d){ state{ borrowAssetsUsd collateralAssetsUsd supplyAssetsUsd utilization borrowApy } } }'
CHURN = 2  # positions opened or closed behind the cursor during a ~1 min walk; a truncated walk misses hundreds


def page(where):
    time.sleep(0.1)  # 750 req/min
    r = graphql(Q, {'w': where})['marketPositions']
    return r['pageInfo']['countTotal'], r['items']


def row(it):
    s = it['state']
    return dict(user=it['user']['address'], collateral=str(s['collateral']), borrow_assets=str(s['borrowAssets']),
                collateral_usd=s['collateralUsd'], borrow_usd=s['borrowAssetsUsd'], health_factor=it['healthFactor'])


def walk(where):
    """Borrow shares change only when the borrower acts, unlike healthFactor, which moves with the oracle and let
    positions slip behind a healthFactor cursor mid-walk. The cursor is a string: the API reads an int filter as a float."""
    seen, lo = {}, '1'
    while True:  # ponytail: >1000 positions with identical borrowShares would stall; the no-new guard breaks instead
        _, items = page(dict(where, borrowShares_gte=lo))
        new = [it for it in items if it['user']['address'].lower() not in seen]
        seen.update((it['user']['address'].lower(), it) for it in new)
        if len(items) < 1000 or not new:
            break
        lo = str(items[-1]['state']['borrowShares'])
    return seen


def fetch(mid):
    """Returns (countTotal, positions). The book is live, so re-walk (up to 3 times) until the count matches
    countTotal; after that accept a gap of CHURN, else raise before anything is written."""
    where = {'chainId_in': [CHAIN], 'marketUniqueKey_in': [mid]}
    for _ in range(3):
        seen = walk(where)
        total, _ = page(dict(where, borrowShares_gte='1'))  # unbanded count, taken right after the walk
        if len(seen) == total:
            break
    if abs(len(seen) - total) > CHURN:
        raise RuntimeError('%s: walked %d positions, countTotal %d after 3 walks' % (mid, len(seen), total))
    return total, [row(it) for it in seen.values()]


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
        assert abs(out['count'] - total) <= CHURN, (name, out['count'], total)
        assert len(users) == len(set(users)), name
        if book > 1e5:  # dust markets round badly
            assert abs(out['borrow_usd_total'] - book) <= 0.01 * book, (name, out['borrow_usd_total'], book)
    print('ok')
