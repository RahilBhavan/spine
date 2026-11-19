"""Read-only risk API over the saved data/summary.json. stdlib only, no keys, no writes.

  GET /v1/markets                    every market's state, plus the book totals
  GET /v1/markets/<market>/capacity  modeled liquidator capacity, its depth inputs and the liquidatable-borrow curve
                                     (<market> is the name, e.g. cbBTC, or its Morpho market id)

Every response carries api_version, snapshot_time (summary.json's generated_at) and source. Numbers are passed
through from summary.json unchanged, so the API and the dashboard agree by construction (tests/test_serve.py).
Responses carry an ETag of the snapshot and Cache-Control; If-None-Match returns 304. Binds 127.0.0.1.

Run: .venv/bin/python -m spine.serve [--port 8001]
"""
import hashlib, json, os, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from spine.api import MARKETS, data_path

API_VERSION = '1'
SOURCE = 'data/summary.json'
MAX_AGE = 300  # seconds a client may reuse a response before revalidating with its ETag
BONUS = '4.38'  # ponytail: capacity inputs at the 4.38% bonus only, as summarize.capacity_ab uses; add ?bonus= if callers need other levels
STATE_FIELDS = ('borrow_usd', 'collateral_usd', 'supply_usd', 'utilization', 'borrow_apy', 'lltv', 'lif', 'bad_debt_ltv',
                'price', 'n_positions', 'coinbase_share_count', 'coinbase_share_borrow', 'capacity_ab_usd', 'distance_to_capacity')
CURVE_FIELDS = ('drop', 'borrow_usd', 'count', 'bad_borrow_usd', 'bad_count')
BY_ID = {m['id']: name for name, m in MARKETS.items()}


def envelope(summary, data):
    return dict(api_version=API_VERSION, snapshot_time=summary['generated_at'], source=SOURCE, data=data)


def market_row(name, state, fields):
    return dict(name=name, market_id=MARKETS.get(name, {}).get('id'), **{k: state.get(k) for k in fields})


def markets(summary):
    return dict(markets=[market_row(n, m['state'], STATE_FIELDS) for n, m in summary['markets'].items()],
                totals=summary['totals'])


def capacity(summary, name):
    m = summary['markets'][name]
    depth = m.get('depth', {})
    return dict(market_row(name, m['state'], ('lltv', 'borrow_usd', 'capacity_ab_usd', 'distance_to_capacity')),
                bonus_pct=float(BONUS),
                dex_capacity_usd=depth.get('dex_capacity_usd', {}).get(BONUS),
                coinbase_bid_depth_usd=depth.get('coinbase', {}).get('bid_depth_usd', {}).get(BONUS),
                liquidatable_curve=[{k: c.get(k) for k in CURVE_FIELDS} for c in m['liquidatable_curve']])


def route(path, summary):
    """(status, body) for a GET path. Pure: no I/O, so the contract tests call it directly too."""
    parts = [p for p in path.split('?', 1)[0].split('/') if p]
    if parts == ['v1', 'markets']:
        return 200, envelope(summary, markets(summary))
    if len(parts) == 4 and parts[:2] == ['v1', 'markets'] and parts[3] == 'capacity':
        name = BY_ID.get(parts[2].lower(), parts[2])
        if name not in summary['markets']:
            return 404, dict(error='unknown market %r' % parts[2], markets=list(summary['markets']))
        return 200, envelope(summary, capacity(summary, name))
    return 404, dict(error='no route %r' % path, routes=['/v1/markets', '/v1/markets/<market>/capacity'])


_snapshot = {}  # path -> (mtime_ns, summary, etag); reloaded when the refresh job rewrites the file


def snapshot(path):
    """(summary, etag) for path, re-read only when its mtime changes."""
    mtime = os.stat(path).st_mtime_ns
    if _snapshot.get(path, (None,))[0] != mtime:
        with open(path, 'rb') as f:
            raw = f.read()
        _snapshot[path] = (mtime, json.loads(raw), '"%s"' % hashlib.sha256(raw).hexdigest()[:16])
    return _snapshot[path][1:]


def handler(path):
    class Handler(BaseHTTPRequestHandler):  # a class only because http.server requires one
        def do_GET(self):
            summary, etag = snapshot(path)
            status, body = route(self.path, summary)
            if status == 200 and self.headers.get('If-None-Match') == etag:
                self.send_response(304)
                self.send_header('ETag', etag)
                self.end_headers()
                return
            raw = json.dumps(body).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(raw)))
            if status == 200:
                self.send_header('ETag', etag)
                self.send_header('Cache-Control', 'public, max-age=%d' % MAX_AGE)
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *a):
            pass
    return Handler


def server(port=8001, path=None):
    return ThreadingHTTPServer(('127.0.0.1', port), handler(path or data_path('summary')))


if __name__ == '__main__':
    args = sys.argv[1:]
    port = int(args[args.index('--port') + 1]) if '--port' in args else 8001
    s, _ = snapshot(data_path('summary'))
    status, body = route('/v1/markets', s)
    assert status == 200 and body['data']['totals'] == s['totals'] and body['snapshot_time'] == s['generated_at']
    cb = route('/v1/markets/%s/capacity' % MARKETS['cbBTC']['id'], s)[1]['data']
    assert cb['name'] == 'cbBTC' and cb['capacity_ab_usd'] == s['markets']['cbBTC']['state']['capacity_ab_usd']
    srv = server(port)
    print('serving %s (snapshot %s) on http://127.0.0.1:%d/v1/markets' % (SOURCE, s['generated_at'], srv.server_address[1]))
    srv.serve_forever()
