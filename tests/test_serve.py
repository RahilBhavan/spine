"""Contract tests for spine.serve: the API returns the same numbers as data/summary.json for the pinned snapshot.
The HTTP tests start a real server on a free local port. Run: .venv/bin/python -m pytest -q tests"""
import json, threading, urllib.error, urllib.request

import pytest

from spine.api import MARKETS, load
from spine.serve import API_VERSION, route, server


@pytest.fixture(scope='module')
def summary():
    s = load('summary')
    if s is None:
        pytest.skip('data/summary.json absent')
    return s


@pytest.fixture(scope='module')
def base():
    s = server(port=0)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield 'http://127.0.0.1:%d' % s.server_address[1]
    s.shutdown()
    s.server_close()


def get(url, headers=None):
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}), timeout=10)
        return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def test_markets_match_summary(summary):
    status, body = route('/v1/markets', summary)
    assert status == 200
    assert (body['api_version'], body['snapshot_time'], body['source']) == (API_VERSION, summary['generated_at'], 'data/summary.json')
    rows = {r['name']: r for r in body['data']['markets']}
    assert set(rows) == set(summary['markets'])
    for name, m in summary['markets'].items():
        for k in ('borrow_usd', 'collateral_usd', 'lltv', 'n_positions', 'capacity_ab_usd', 'distance_to_capacity'):
            assert rows[name][k] == m['state'][k], (name, k)
        assert rows[name]['market_id'] == MARKETS[name]['id']
    assert body['data']['totals'] == summary['totals']
    assert sum(r['n_positions'] for r in rows.values()) == summary['totals']['n_positions']


def test_capacity_matches_summary(summary):
    for name, m in summary['markets'].items():
        status, body = route('/v1/markets/%s/capacity' % name, summary)
        assert status == 200 and body['snapshot_time'] == summary['generated_at']
        d = body['data']
        assert d['capacity_ab_usd'] == m['state']['capacity_ab_usd']
        assert d['distance_to_capacity'] == m['state']['distance_to_capacity']
        assert [(c['drop'], c['borrow_usd'], c['count']) for c in d['liquidatable_curve']] == \
               [(c['drop'], c['borrow_usd'], c['count']) for c in m['liquidatable_curve']]
        # distance_to_capacity is the first drop where liquidatable borrow exceeds capacity (spine.summarize)
        if d['capacity_ab_usd'] and d['distance_to_capacity'] is not None:
            first = next(c['drop'] for c in d['liquidatable_curve'] if c['borrow_usd'] > d['capacity_ab_usd'])
            assert first == d['distance_to_capacity'], name


def test_unknown_routes(summary):
    status, body = route('/v1/markets/NOPE/capacity', summary)
    assert status == 404 and 'cbBTC' in body['markets']
    assert route('/v2/markets', summary)[0] == 404
    assert route('/v1/markets/cbBTC', summary)[0] == 404


def test_http_round_trip_and_cache(summary, base):
    status, headers, raw = get(base + '/v1/markets')
    assert status == 200 and headers['Content-Type'] == 'application/json'
    assert 'max-age' in headers['Cache-Control']
    assert json.loads(raw) == json.loads(json.dumps(route('/v1/markets', summary)[1]))
    assert get(base + '/v1/markets', {'If-None-Match': headers['ETag']})[0] == 304
    assert get(base + '/v1/markets', {'If-None-Match': '"stale"'})[0] == 200
    status, _, raw = get(base + '/v1/markets/cbBTC/capacity')
    assert status == 200 and json.loads(raw)['data']['name'] == 'cbBTC'
    status, headers, raw = get(base + '/v1/markets/NOPE/capacity')
    assert status == 404 and 'ETag' not in headers and 'error' in json.loads(raw)


def test_new_snapshot_is_served_without_restart(summary, tmp_path):
    p = tmp_path / 'summary.json'
    p.write_text(json.dumps(summary))
    s = server(port=0, path=str(p))
    threading.Thread(target=s.serve_forever, daemon=True).start()
    url = 'http://127.0.0.1:%d/v1/markets' % s.server_address[1]
    try:
        _, h1, raw = get(url)
        assert json.loads(raw)['snapshot_time'] == summary['generated_at']
        p.write_text(json.dumps(dict(summary, generated_at='2030-01-01T00:00:00+00:00')))
        _, h2, raw = get(url)
        assert json.loads(raw)['snapshot_time'] == '2030-01-01T00:00:00+00:00' and h2['ETag'] != h1['ETag']
    finally:
        s.shutdown()
        s.server_close()
