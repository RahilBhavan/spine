"""Shape checks for the JSON the site reads. Missing files skip so CI without data still runs the rest."""
import pytest
from spine.api import load


def need(name):
    d = load(name)
    if d is None:
        pytest.skip('data/%s.json absent' % name)
    return d


def test_summary():
    s = need('summary')
    assert {'generated_at', 'markets', 'totals'} <= set(s)
    assert s['markets']
    for m, v in s['markets'].items():
        assert {'borrow_usd', 'collateral_usd', 'lltv', 'lif'} <= set(v['state']), m
        assert len(v['ltv_hist']) == 50, m
        curve = v['liquidatable_curve']
        assert len(curve) == 71, m
        b = [pt['borrow_usd'] for pt in curve]
        assert all(x <= y for x, y in zip(b, b[1:])), m


def test_backtest():
    b = need('backtest')
    assert b['runs']
    keys = {'market', 'window', 'lltv', 'cap', 'scenario', 'resp_share', 'react_min', 'margin', 'cex_cap_usd', 'book',
            'liquidated_usd', 'realized_bad_debt_usd', 'unrealized_bad_debt_usd'}
    for r in b['runs']:
        assert keys <= set(r), keys - set(r)
    assert {'resp_share', 'react_min'} <= set(b['calibrated'] or {})
    assert b['latest_book'] and all(r['book'] != 'today' for r in b['runs'])  # live rows are keyed by book date since Phase G1
    assert {'cbXRP', 'SOL'} <= {r['market'] for r in b['runs']}  # alt replays, Phase G2


def test_calibration():
    c = need('calibration')
    assert c['windows']
    for w, v in c['windows'].items():
        if 'cbBTC' in v:
            assert {'volume', 'bonus', 'latency', 'liquidators'} <= set(v['cbBTC']), w
    board = c['leaderboard']
    assert board
    keys = {'address', 'count', 'repaid_usd', 'seized_usd', 'gross_bonus_usd', 'windows', 'latency_p50', 'is_contract', 'coinbase_affiliated'}
    for r in board:
        assert keys <= set(r), keys - set(r)
        assert r['latency_p50'] is None or r['latency_p50'] >= 0, r
    assert all(x['repaid_usd'] >= y['repaid_usd'] for x, y in zip(board, board[1:]))


def test_oracle_lag():
    o = need('oracle_lag')
    keys = {'n_updates', 'interval_s', 'deviation', 'low', 'oracle_low', 'oracle_low_gap_pct', 'lag_to_low_s'}
    for w, assets in o.items():
        if w == 'generated_at':
            continue
        for asset, s in assets.items():
            assert keys <= set(s), (w, asset, keys - set(s))
            assert 0 <= s['deviation']['p50'] <= 0.02, (w, asset)


def test_vaults():
    d = need('vaults')
    for m, v in d['markets'].items():
        assert v['supply_usd'] >= 0 and isinstance(v['vaults'], list) and v['vaults'], m
        assert all(x['supplied_usd'] >= 0 for x in v['vaults']), m
        assert sum(x['share'] for x in v['vaults']) <= 1.02, m
