"""Read-only risk API over the saved data/summary.json. stdlib only, no keys, no writes.

  GET /v1/markets                  every market's state, plus the book totals
  GET /v1/markets/<name>/capacity  modeled liquidator capacity, its depth inputs and the liquidatable-borrow curve

Every response carries api_version, snapshot_time (summary.json's generated_at) and source. Numbers are passed
through from summary.json unchanged, so the API and the dashboard agree by construction (tests/test_serve.py).
Responses carry an ETag of the snapshot and Cache-Control; If-None-Match returns 304.

Run: .venv/bin/python -m spine.serve [--host 127.0.0.1] [--port 8001]
"""
import argparse, hashlib, json, os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from spine.api import MARKETS, data_path

API_VERSION = '1'
SOURCE = 'data/summary.json'
MAX_AGE = 300  # seconds; the refresh job runs every few hours
STATE_FIELDS = ('borrow_usd', 'collateral_usd', 'supply_usd', 'utilization', 'borrow_apy', 'lltv', 'lif', 'price',
                'n_positions', 'coinbase_share_borrow', 'capacity_ab_usd', 'distance_to_capacity')
CURVE_FIELDS = ('drop', 'borrow_usd', 'count', 'bad_borrow_usd', 'bad_count')


def envelope(summary, data):
    return dict(api_version=API_VERSION, snapshot_time=summary['generated_at'], source=SOURCE, data=data)


def markets(summary):
    rows = [dict(name=name, market_id=MARKETS.get(name, {}).get('id'),
                 **{k: m['state'].get(k) for k in STATE_FIELDS}) for name, m in summary['markets'].items()]
    return dict(markets=rows, totals=summary['totals'])


def capacity(summary, name):
    m = summary['markets'][name]
    st, depth = m['state'], m.get('depth', {})
    return dict(name=name, market_id=MARKETS.get(name, {}).get('id'), lltv=st.get('lltv'), borrow_usd=st.get('borrow_usd'),
                capacity_ab_usd=st.get('capacity_ab_usd'), distance_to_capacity=st.get('distance_to_capacity'),
                inputs_at_bonus_4_38=dict(dex_capacity_usd=depth.get('dex_capacity_usd', {}).get('4.38'),
                                          coinbase_bid_depth_usd=depth.get('coinbase', {}).get('bid_depth_usd', {}).get('4.38')),
                liquidatable_curve=[{k: c.get(k) for k in CURVE_FIELDS} for c in m['liquidatable_curve']])


def route(path, summary):
    """(status, body) for a GET path. Pure: no I/O, so the contract tests call it directly too."""
    parts = [p for p in path.split('?', 1)[0].split('/') if p]
    if parts == ['v1', 'markets']:
        return 200, envelope(summary, markets(summary))
    if len(parts) == 4 and parts[:2] == ['v1', 'markets'] and parts[3] == 'capacity':
        if parts[2] not in summary['markets']:
            return 404, dict(error='unknown market %r' % parts[2], markets=list(summary['markets']))
        return 200, envelope(summary, capacity(summary, parts[2]))
    return 404, dict(error='no route %r' % path, routes=['/v1/markets', '/v1/markets/<name>/capacity'])


class Snapshot:
    """summary.json, reloaded when its mtime changes, with an ETag of its bytes."""
    def __init__(self, path):
        self.path, self.mtime, self.summary, self.etag = path, None, None, None

    def get(self):
        mtime = os.stat(self.path).st_mtime_ns
        if mtime != self.mtime:
            raw = open(self.path, 'rb').read()
            self.summary, self.etag, self.mtime = json.loads(raw), '"%s"' % hashlib.sha256(raw).hexdigest()[:16], mtime
        return self.summary, self.etag


def handler(snapshot):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            summary, etag = snapshot.get()
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


def server(host='127.0.0.1', port=8001, path=None):
    return ThreadingHTTPServer((host, port), handler(Snapshot(path or data_path('summary'))))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=8001)
    a = ap.parse_args()
    s = server(a.host, a.port)
    print('serving %s on http://%s:%d/v1/markets' % (SOURCE, a.host, s.server_address[1]))
    s.serve_forever()
