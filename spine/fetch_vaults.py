"""Who funds each market: MetaMorpho (V1) vaults from the Morpho API, Vault V2s read on-chain through their adapters -> data/vaults.json.
Morpho socializes bad debt pro rata to suppliers, so a vault's share of market supply is its share of any loss."""
import time, datetime as dt
from spine.api import graphql, rpc, save, argv_max_seconds, budget, MARKETS, CHAIN, MORPHO_BLUE, LOAN_DECIMALS

# 4-byte selectors (stdlib has no keccak; verified with `cast sig`).
MARKET_SEL = '5c60e39a'          # Morpho Blue market(bytes32) -> (totalSupplyAssets, totalSupplyShares, ...)
POSITION_SEL = '93c52062'        # Morpho Blue position(bytes32,address) -> (supplyShares, borrowShares, collateral)
ADAPTERS_LEN_SEL = '5aa22bc8'    # Vault V2 adaptersLength()
ADAPTERS_SEL = '4ef501ac'        # Vault V2 adapters(uint256); V2 vaults hold Morpho positions through these, not directly
TOTAL_ASSETS_SEL = '01e1d114'    # ERC-4626 totalAssets()
# ponytail: keyless public node. mainnet.base.org 429s past ~5 calls in a burst and the ~120 reads here took over the budget; swap back if this one dies.
RPC = 'https://base-rpc.publicnode.com'
QUERY = '''query($id: String!, $chain: Int!) { marketById(marketId: $id, chainId: $chain) { state { supplyAssetsUsd }
  supplyingVaults { address name state { totalAssetsUsd allocation { market { marketId } supplyAssetsUsd } } }
  supplyingVaultV2s { address name } } }'''


def call(to, data):
    """eth_call result hex, or None on revert or empty."""
    time.sleep(0.1)
    try:
        r = rpc('eth_call', [{'to': to, 'data': '0x' + data}, 'latest'], url=RPC)
    except RuntimeError as e:
        if 'revert' in str(e).lower():
            return None
        raise
    return r if len(r) >= 66 else None


def word(x, i=0):
    return None if x is None else int(x[2 + 64 * i:66 + 64 * i], 16)


def market_vaults(name, cache):
    m = graphql(QUERY, {'id': MARKETS[name]['id'], 'chain': CHAIN})['marketById']
    supply, mid = m['state']['supplyAssetsUsd'], MARKETS[name]['id'][2:]
    rows = []
    for v in m['supplyingVaults']:
        alloc = next((a['supplyAssetsUsd'] for a in v['state']['allocation'] if a['market']['marketId'] == MARKETS[name]['id']), 0) or 0
        rows.append(dict(address=v['address'], name=v['name'], kind='v1', supplied_usd=alloc, vault_total_usd=v['state']['totalAssetsUsd']))
    mk = call(MORPHO_BLUE, MARKET_SEL + mid)
    assets, shares = word(mk, 0), word(mk, 1)
    for v in m['supplyingVaultV2s']:
        a = v['address']
        if a not in cache:  # adapters and totalAssets are per vault, shared across markets
            n = word(call(a, ADAPTERS_LEN_SEL)) or 0
            t = word(call(a, TOTAL_ASSETS_SEL))
            cache[a] = dict(adapters=['0x' + call(a, ADAPTERS_SEL + '%064x' % i)[-40:] for i in range(n)], total=None if t is None else t / 10 ** LOAN_DECIMALS)
        ss = sum(word(call(MORPHO_BLUE, POSITION_SEL + mid + '%064x' % int(ad, 16))) or 0 for ad in cache[a]['adapters'])
        rows.append(dict(address=a, name=v['name'], kind='v2', supplied_usd=ss * assets / shares / 10 ** LOAN_DECIMALS if shares else 0,
                         vault_total_usd=cache[a]['total']))  # USDC at $1; the API prices V1 the same way
    rows = sorted((r for r in rows if r['supplied_usd'] > 0), key=lambda r: -r['supplied_usd'])
    rows.append(dict(address=None, name='other suppliers', kind='direct', supplied_usd=max(0, supply - sum(r['supplied_usd'] for r in rows)), vault_total_usd=None))
    for r in rows:
        r['share'] = r['supplied_usd'] / supply if supply else 0
    return dict(supply_usd=supply, vaults=rows)


def fetch_all(ok):
    """Markets in MARKETS order until the budget runs out; a market past the budget is left out rather than half-read."""
    cache, markets = {}, {}
    for n in MARKETS:
        if not ok():
            break
        markets[n] = market_vaults(n, cache)
    return dict(generated_at=dt.datetime.now(dt.timezone.utc).isoformat(), markets=markets)


if __name__ == '__main__':
    max_seconds, _, _ = argv_max_seconds()
    ok = budget(max_seconds)
    d = fetch_all(ok)
    save('vaults', d, indent=1)
    for n, m in d['markets'].items():
        vs = m['vaults'][:-1]
        print(f"{n:8} supply {m['supply_usd'] / 1e6:8,.1f}M  {len(vs):2} vaults cover {sum(v['share'] for v in vs):5.1%}  "
              f"(v1 {sum(v['share'] for v in vs if v['kind'] == 'v1'):5.1%}, v2 {sum(v['share'] for v in vs if v['kind'] == 'v2'):5.1%})")
        assert sum(v['supplied_usd'] for v in vs) <= 1.02 * m['supply_usd'], n
        assert sum(v['share'] for v in m['vaults']) <= 1.02, n
    print('complete' if len(d['markets']) == len(MARKETS) else 'partial, rerun to continue')
