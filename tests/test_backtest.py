"""Brute-force per-position reference for spine.backtest.simulate on a synthetic book and path (ROADMAP Phase C).
Run: .venv/bin/python -m pytest -q tests"""
import math
import numpy as np
from spine.api import lif
from spine.backtest import DEFAULTS, DAY_STEPS, book_arrays, capacity, reshape, simulate

P0, LLTV = 100.0, 0.86


def synthetic_book(n=1500, seed=0):
    """Same dict schema as data/positions_cbBTC.json: collateral units lognormal, LTV uniform 0.3-0.85 at P0."""
    rng = np.random.default_rng(seed)
    units = np.round(rng.lognormal(math.log(10), 1.0, n), 8)  # ~$1000 of collateral each at P0
    ltv = rng.uniform(0.3, 0.85, n)
    pos = []
    for u, l in zip(units.tolist(), ltv.tolist()):
        cusd = u * P0
        pos.append(dict(user='0x%040x' % int(rng.integers(0, 2 ** 63)), collateral=str(int(round(u * 1e8))),
                        borrow_assets=str(int(round(cusd * l * 1e6))), collateral_usd=cusd, borrow_usd=cusd * l, health_factor=LLTV / l))
    return dict(market='cbBTC', lltv=LLTV, count=n, positions=pos)


def candles(prices, t0=1_700_000_000):
    """5-min [ts, o, h, l, c] rows with o = h = l = c."""
    return [[t0 + 300 * i, p, p, p, p] for i, p in enumerate(prices)]


def slide(pct_per_day, days, p=P0):
    return [p * (1 - pct_per_day) ** (t / DAY_STEPS) for t in range(days * DAY_STEPS)]


def crash_candles():
    """2%/day for 3 days, then -40% over 4 hours, then flat for a day."""
    s = slide(0.02, 3)
    cliff = [s[-1] * (1 - 0.4 * k / 48) for k in range(1, 49)]
    return candles(s + cliff + [cliff[-1]] * DAY_STEPS)


def lows(c):
    return np.array([r[3] for r in c], float)


def params(**kw):
    return dict(dict(DEFAULTS, lltv=LLTV, base_eff=(np.inf, 0.0)), **kw)


def reference(coll, debt, path, base_a=np.inf, r=DEFAULTS['r'], lag=DEFAULTS['lag_bars']):
    """Plain loop over steps and positions. Oracle lags the path; a position joins the queue when LTV > lltv at the oracle
    price, is served largest-debt-first (static rank on initial debt) up to the Tier A pool avail (replenished r*base per
    step, market-valued), seized in full min(debt*LIF, coll*p) or partially for the last one that does not fit;
    shortfall max(0, debt - coll*p/LIF) at the liquidation step. base_a = inf is scenario ABC."""
    L = lif(LLTV)
    coll, debt = list(map(float, coll)), list(map(float, debt))
    n = len(debt)
    by_debt = sorted(range(n), key=lambda i: -debt[i])
    alive = [True] * n
    oracle = [path[0]] * lag + list(path[:len(path) - lag])
    avail, seized, realized, n_liq = base_a, 0.0, 0.0, 0
    for p, pm in zip(oracle, path):
        avail = min(base_a, avail + r * base_a)
        f = pm / p
        if L * f <= 1:
            continue
        budget, step = avail / f, 0.0
        for i in by_debt:
            if not (alive[i] and debt[i] / (coll[i] * p) > LLTV):
                continue
            s = min(debt[i] * L, coll[i] * p)
            if s <= budget - step:
                realized += max(0.0, debt[i] - coll[i] * p / L)
                alive[i], n_liq, step = False, n_liq + 1, step + s
                debt[i] = coll[i] = 0.0
            else:
                left = budget - step
                debt[i] -= left / L
                coll[i] -= left / p
                step = budget
                break
        seized += step
        avail -= min(step * f, avail)
    return dict(liquidated_usd=seized, repaid_usd=seized / L, n_liquidated=n_liq, realized_bad_debt_usd=realized)


def test_reference_abc_and_a():
    coll, debt, p_book, h = book_arrays(synthetic_book(), 'cbBTC')
    assert len(debt) == 1500 and abs(p_book - P0) < 1e-9
    path = lows(crash_candles())
    ref = reference(coll, debt, path)
    sim = simulate((coll, debt, h), path, params(scenario='ABC'))
    assert sim['n_liquidated'] == ref['n_liquidated'] > 0
    for k in ('liquidated_usd', 'repaid_usd', 'realized_bad_debt_usd'):
        assert math.isclose(sim[k], ref[k], rel_tol=1e-9), (k, sim[k], ref[k])
    # scenario A: depth dict shaped like data/depth.json, so capacity() is exercised the way run() calls it
    depth = dict(dex=dict(cbBTC=dict(capacity_usd_at_slippage={'1': dict(usd=5000.0), '5': dict(usd=5000.0)})), cex={})
    ps = params(scenario='A', k_dex=1.0)
    ps['base_eff'] = capacity(depth, 'cbBTC', LLTV, ps)
    assert ps['base_eff'] == (5000.0, 0.0)
    ref_a = reference(coll, debt, path, base_a=5000.0)
    sim_a = simulate((coll, debt, h), path, ps)
    assert ref_a['liquidated_usd'] < ref['liquidated_usd']  # capacity binds
    assert math.isclose(sim_a['liquidated_usd'], ref_a['liquidated_usd'], rel_tol=0.01), (sim_a['liquidated_usd'], ref_a['liquidated_usd'])
    assert sim_a['n_liquidated'] == ref_a['n_liquidated']
    assert ref_a['realized_bad_debt_usd'] > 0  # queued positions ride the 40% leg past 1/LIF while capacity is exhausted
    assert math.isclose(sim_a['realized_bad_debt_usd'], ref_a['realized_bad_debt_usd'], rel_tol=0.01)


def test_borrower_response_time_dependence():
    coll, debt, _, h = book_arrays(synthetic_book(), 'cbBTC')
    book = (coll, debt, h)
    slow = lows(candles(slide(0.02, 10)))
    base = simulate(book, slow, params(scenario='ABC', resp_share=0.0, react_min=60))
    resp = simulate(book, slow, params(scenario='ABC', resp_share=0.7, react_min=60))
    assert base['cured_usd'] == 0 and resp['cured_usd'] > 0
    assert 0 < resp['n_liquidated'] < base['n_liquidated'] and resp['liquidated_usd'] < base['liquidated_usd']
    cliff = lows(candles([P0, P0 * 0.6] + [P0 * 0.6] * 8))  # shorter than react_min after the drop: no cure anywhere
    c = simulate(book, cliff, params(scenario='ABC', resp_share=0.7, react_min=60))
    assert c['cured_usd'] == 0 and c['n_liquidated'] > 0


def test_tier_b_ring_window():
    # Spec: Tier B cap is a strict DAY_STEPS-bar rolling window; one clearance per window at steps 1, 289, 577 (and 865
    # on a 1000-bar path with five positions). Written to the spec; a ring that rolls off one bar late fails here.
    syn = (np.ones(5), np.ones(5), np.full(5, 0.5))  # each seizes exactly 1.0 at p = 1 (debt*LIF > coll*p)
    ps = params(base_eff=(0.0, 1.0), cex_cap_usd=1.0, r=1.0, lag_bars=0, resp_share=0.0)
    path = np.array([10.0] + [1.0] * 999)  # liquidatable from step 1 on
    n_at = lambda bars: simulate(syn, path[:bars], ps)['n_liquidated']
    assert n_at(1) == 0 and n_at(2) == 1
    steps = []
    for t in (1, 1 + DAY_STEPS, 1 + 2 * DAY_STEPS, 1 + 3 * DAY_STEPS):
        assert n_at(t) == len(steps), (t, n_at(t))  # nothing clears on the bar before
        assert n_at(t + 1) == len(steps) + 1, (t + 1, n_at(t + 1))
        steps.append(t)
    assert steps == [1, 1 + 288, 1 + 576, 1 + 864] and n_at(1000) == 4
    assert simulate(syn, path[:578], ps)['queue_minutes_p50'] == DAY_STEPS * 5


def test_reshape():
    coll, debt, p_book, _ = book_arrays(synthetic_book(), 'cbBTC')
    old = debt / (coll * p_book)
    new = reshape(coll, debt, p_book, p_book, 0.80, 0.60) / (coll * p_book)
    assert np.allclose(new, 0.8 * old, rtol=1e-12) and new.max() <= 0.80 * 0.99 + 1e-12
