"""Stress-grid replay on small fixed fixtures (no data/ files): the synthetic cbBTC book and crash path of tests/test_backtest.py."""
import math
import numpy as np
from spine.backtest import book_arrays, simulate
from spine.stress_grid import COLUMNS, cell, clean_paths, read_csv, table, write_csv
from tests.test_backtest import params, synthetic_book, crash_candles

DEPTH = dict(dex=dict(cbBTC=dict(capacity_usd_at_slippage={'1': dict(usd=20000.0), '10': dict(usd=20000.0)})),
             cex={'coinbase': {'BTC-USD': dict(bid_depth_usd={'1': 100000.0, '10': 100000.0})}})
STAR = (0.0, 60, 0.0)


def replay(mult):
    book = book_arrays(synthetic_book(), 'cbBTC')
    return cell(book, DEPTH, crash_candles(), 'Mar2020', 0.86, 0.75, mult, STAR, book_date='2000-01-01', depth_date='2000-01-02', supply=book[1].sum() / 0.9)[0]


def test_replay_on_fixture_is_deterministic_and_labelled():
    a, b = replay(1), replay(1)
    assert a == b
    assert a['book_date'] == '2000-01-01' and a['depth_date'] == '2000-01-02' and a['crash_path'] == 'Mar2020' and a['lltv'] == 0.86
    assert math.isclose(a['underwater_unserved_at_trough_usd'], 75458.48, abs_tol=0.01) and math.isclose(a['realized_loss_usd'], 75458.48, abs_tol=0.01)
    assert a['binds_first'] == 'depth' and a['capital_cap_binds_hour'] is None


def test_capital_levels_move_the_two_measures_separately():
    tight, mid, unlimited = replay(1e-6), replay(1e-3), replay(math.inf)
    assert tight['binds_first'] == 'capital' and tight['capital_cap_binds_hour'] == tight['binds_first_hour']
    assert mid['binds_first'] == 'depth' and mid['capital_cap_binds_hour'] > mid['binds_first_hour']
    assert unlimited['capital_cap_binds_hour'] is None and unlimited['liquidator_capital_usd_per_day'] == 'unlimited'
    # less capital leaves more underwater and unserved at the trough and more realized loss; the end-of-path leftover appears only when the cap strands a queue
    assert tight['underwater_unserved_at_trough_usd'] > mid['underwater_unserved_at_trough_usd'] > unlimited['underwater_unserved_at_trough_usd']
    assert tight['realized_loss_usd'] > mid['realized_loss_usd'] > unlimited['realized_loss_usd']
    assert tight['underwater_at_end_usd'] > 0 == mid['underwater_at_end_usd']
    assert 'total' not in ' '.join(COLUMNS)  # the two measures are never summed into one column


def test_first_bind_classification():
    syn = (np.ones(5), np.ones(5), np.full(5, 0.5))  # five positions that each seize exactly 1.0 at p = 1 (tests/test_backtest.py ring fixture)
    path = np.array([10.0] + [1.0] * 20)
    ps = params(base_eff=(0.0, 1.0), cex_cap_usd=1.0, r=1.0, lag_bars=0, resp_share=0.0)
    r = simulate(syn, path, ps)
    assert (r['first_bind'], r['first_bind_step'], r['capital_bind_step']) == ('depth', 1, 2)  # step 1: depth 1.0 = cap, so depth; step 2: the 24h cap is spent
    r = simulate(syn, path, dict(ps, cex_cap_usd=0.5))
    assert (r['first_bind'], r['first_bind_step'], r['capital_bind_step']) == ('capital', 1, 1)
    r = simulate(syn, path, dict(ps, base_eff=(np.inf, 0.0)))
    assert (r['first_bind'], r['first_bind_step'], r['capital_bind_step']) == (None, -1, -1)
    # one position at LTV 0.8; at step 2 the lagged oracle (0.8) puts it over the line while the market (0.5) is far below the oracle: the bonus is gone
    gap = simulate((np.ones(1), np.full(1, 0.8), np.full(1, 0.5)), np.array([1.0, 0.8, 0.5, 0.5]), params(base_eff=(np.inf, 0.0), lag_bars=1, resp_share=0.0))
    assert (gap['first_bind'], gap['first_bind_step']) == ('oracle_gap', 2)


def test_csv_round_trip_and_table(tmp_path):
    rows = [replay(1), replay(math.inf)]
    f = tmp_path / 'grid.csv'
    write_csv(rows, f)
    back = read_csv(f)
    assert [r['book_date'] for r in back] == ['2000-01-01'] * 2 and set(back[0]) == set(COLUMNS)
    md = table(back, ['Mar2020']).splitlines()
    assert len(md) == 4 and all(l.startswith('| 2000-01-01 | Mar 2020 | 86% / 75% |') for l in md[2:]) and 'unlimited' in md[3]
    assert 'Mar2020' not in clean_paths(back)
    zero = dict(back[0], underwater_unserved_at_trough_usd='0', realized_loss_usd='0')
    assert 'Mar2020' in clean_paths([zero])
