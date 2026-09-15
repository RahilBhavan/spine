"""Shared HTTP helpers. stdlib only. Every fetcher goes through these."""
import json, time, urllib.request, urllib.parse, urllib.error

MORPHO = 'https://blue-api.morpho.org/graphql'
BASE_RPC = 'https://mainnet.base.org'
COINBASE = 'https://api.exchange.coinbase.com'
CHAIN = 8453
MORPHO_BLUE = '0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb'
UA = {'User-Agent': 'spine-risk-dashboard', 'Content-Type': 'application/json'}

# Coinbase-linked Morpho markets on Base. lltv as a fraction. decimals = collateral token decimals.
MARKETS = {
    'cbBTC':   dict(id='0x9103c3b4e834476c9a62ea009ba2c884ee42e94e6e314a26f04d312434191836', lltv=0.86,  decimals=8,  cb_product='BTC-USD'),
    'WETH':    dict(id='0x8793cf302b8ffd655ab97bd1c695dbd967807e8367a65cb2f4edaf1380ba1bda', lltv=0.86,  decimals=18, cb_product='ETH-USD'),
    'cbETH':   dict(id='0x0ca10126f6c94cbd9cf0a48cc9516ae5e3dec5aa68303e6d988ee37c5149bf0d', lltv=0.77,  decimals=18, cb_product='ETH-USD'),
    'cbXRP':   dict(id='0xd4a903dc6d949519060c7707f9604fdc9772c046e05c2e3a8fce0bd7196e4109', lltv=0.625, decimals=6,  cb_product='XRP-USD'),
    'SOL':     dict(id='0x7dc02ff6c536b1d49d7fba770438d79f5bd1f1c78884629b7d1aaee19675782b', lltv=0.625, decimals=9,  cb_product='SOL-USD'),
    'cbDOGE':  dict(id='0x73527ddd796e6d4f48387adaae36f6f3d49d606d7f2a15eb0c931416a58875d8', lltv=0.625, decimals=8,  cb_product='DOGE-USD'),
    'cbADA':   dict(id='0xd7520ad198b497b6eb75bc690268f4597630dbc12e305e9d4105843bab36e41d', lltv=0.625, decimals=6,  cb_product='ADA-USD'),
    'cbLTC':   dict(id='0x9125d0fa03c3137166df68bcc72283477830de2a4a5536512374c573ad4583c3', lltv=0.625, decimals=8,  cb_product='LTC-USD'),
    'JitoSOL': dict(id='0x09276541cfecb6920a80679a1deced4dde3ae64bf5fc2c9c1f9c21e0c152e1a5', lltv=0.625, decimals=9,  cb_product='SOL-USD'),
}
LOAN_DECIMALS = 6  # USDC


def lif(lltv):
    """Morpho liquidation incentive factor."""
    return min(1.15, 1 / (0.3 * lltv + 0.7))


def _post(url, body, retries=6):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=UA)
            return json.load(urllib.request.urlopen(req, timeout=60))
        except urllib.error.HTTPError as e:
            if e.code == 400:  # GraphQL validation error: not retryable, show the body
                raise RuntimeError(e.read().decode()[:500])
            if i == retries - 1:
                raise
            time.sleep(4 * 2 ** i if e.code == 429 else 1.5 ** i)  # public RPCs rate-limit hard; back off for real
        except Exception:  # ponytail: blanket retry with backoff; refine per status if it bites
            if i == retries - 1:
                raise
            time.sleep(1.5 ** i)


def graphql(query, variables=None):
    r = _post(MORPHO, {'query': query, 'variables': variables or {}})
    if r.get('errors'):
        raise RuntimeError(r['errors'])
    return r['data']


def rpc(method, params, url=BASE_RPC):
    r = _post(url, {'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params})
    if 'error' in r:
        raise RuntimeError(r['error'])
    return r['result']


def coinbase_get(path, **params):
    q = ('?' + urllib.parse.urlencode(params)) if params else ''
    req = urllib.request.Request(COINBASE + path + q, headers=UA)
    time.sleep(0.12)  # public limit 10 req/s
    return json.load(urllib.request.urlopen(req, timeout=60))


if __name__ == '__main__':
    assert abs(lif(0.86) - 1.04384) < 1e-4 and abs(lif(0.625) - 1.1274) < 1e-3
    m = graphql('{ marketById(marketId: "%s", chainId: %d) { lltv state { borrowAssetsUsd } } }' % (MARKETS['cbBTC']['id'], CHAIN))
    assert int(m["marketById"]['lltv']) == 860000000000000000
    print('ok, cbBTC borrow $%.0fM' % (m["marketById"]['state']['borrowAssetsUsd'] / 1e6))
