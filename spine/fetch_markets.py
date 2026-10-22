"""Every Morpho Blue market on Base with at least MIN_BORROW_USD borrowed -> data/base_markets.json.
Market-level state only (one paged query, about a second): summarize folds it into summary.json's base_markets, which the
site's "All Base markets" table and the loan check read. The nine Coinbase markets in api.MARKETS carry their name in `tracked`.
Run: .venv/bin/python -m spine.fetch_markets [--check]"""
import sys, time
from spine.api import graphql, MARKETS, CHAIN, save

MIN_BORROW_USD = 10e6
Q = '''query($s:Int,$min:Float){ markets(first:100, skip:$s, orderBy:BorrowAssetsUsd, orderDirection:Desc,
  where:{chainId_in:[%d], borrowAssetsUsd_gte:$min}){ pageInfo{countTotal} items{ marketId lltv listed warnings{type}
  collateralAsset{symbol name address price{usd}} loanAsset{symbol}
  state{borrowAssetsUsd supplyAssetsUsd collateralAssetsUsd utilization borrowApy} } } }''' % CHAIN
TRACKED = {m['id']: name for name, m in MARKETS.items()}


def row(it):
    c, s = it['collateralAsset'] or {}, it['state']
    return dict(id=it['marketId'], tracked=TRACKED.get(it['marketId']), collateral=c.get('symbol'), collateral_name=c.get('name'),
                collateral_address=c.get('address'), loan=it['loanAsset']['symbol'], lltv=int(it['lltv']) / 1e18,
                listed=it['listed'], warnings=sorted(w['type'] for w in it['warnings']),
                collateral_price_usd=(c.get('price') or {}).get('usd'), borrow_usd=s['borrowAssetsUsd'], supply_usd=s['supplyAssetsUsd'],
                collateral_usd=s['collateralAssetsUsd'], utilization=s['utilization'], borrow_apy=s['borrowApy'])


def fetch(min_borrow=MIN_BORROW_USD):
    """All markets at or above min_borrow, largest first. Raises if the pages do not add up to countTotal."""
    out, total = [], None
    while total is None or len(out) < total:
        r = graphql(Q, {'s': len(out), 'min': min_borrow})['markets']
        total = r['pageInfo']['countTotal']
        if not r['items']:
            break
        out += [row(it) for it in r['items']]
    if len(out) != total:
        raise RuntimeError('fetched %d markets, countTotal %d' % (len(out), total))
    return out


if __name__ == '__main__':
    markets = fetch()
    save('base_markets', dict(fetched_at=int(time.time()), min_borrow_usd=MIN_BORROW_USD, markets=markets), separators=(',', ':'))
    listed = [m for m in markets if m['listed']]
    print('%d Base markets with >= $%.0fM borrowed ($%.0fM total): %d listed by Morpho, %d unlisted, tracked here: %s' % (
        len(markets), MIN_BORROW_USD / 1e6, sum(m['borrow_usd'] for m in markets) / 1e6, len(listed), len(markets) - len(listed),
        ', '.join(m['tracked'] for m in markets if m['tracked'])))
    ids = [m['id'] for m in markets]
    assert len(ids) == len(set(ids)) and all(m['borrow_usd'] >= MIN_BORROW_USD for m in markets)
    assert all(a['borrow_usd'] >= b['borrow_usd'] for a, b in zip(markets, markets[1:]))
    assert all(0 < m['lltv'] < 1 for m in markets)
    if '--check' in sys.argv[1:]:  # level check: the $1.6B cbBTC market is in the list and tagged
        assert 'cbBTC' in {m['tracked'] for m in markets}
    print('ok')
