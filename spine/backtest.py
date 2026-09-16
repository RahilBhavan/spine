"""Liquidation-queue backtest (PLAN.md section 4) -> data/backtest.json. numpy; run with .venv/bin/python.
Run: .venv/bin/python -m spine.backtest [grid|sens|calib|all] [--market cbBTC]
Results append to data/backtest.json (deduped on parameters) so the grid can be split across invocations."""
import json, os, sys, time, glob
import numpy as np
from spine.api import MARKETS, lif
from spine.fetch_prices import WINDOWS

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
OUT = os.path.join(DATA, 'backtest.json')
BAR_MIN = 5
DEFAULTS = dict(lltv=0.86, cap=0.75, scenario='AB', k_dex=0.5, k_cex=0.3, r=0.2, lag_bars=1, reshape=True,
                warn_gap=0.06, resp_share=0.0, react_min=60, cure=0.0)
SHARES, REACTS = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9], [15, 30, 60, 120, 240]
# calibration books: (window in fetch_oracle/calibrate naming, price window, book date, markets)
CALIB = [('Feb2026', 'Feb2026', '2026-02-03', ['cbBTC', 'WETH']), ('Jun2026a', 'Jun2026', '2026-06-01', ['cbBTC', 'WETH']),
         ('Oct2025', 'Oct2025', '2025-10-09', ['cbBTC'])]
ORACLE_ASSET = {'cbBTC': 'BTC', 'WETH': 'ETH'}


def load(path):
    return json.load(open(path))


def book_arrays(raw, market):
    """(collateral units, debt usd, book price, responsiveness hash in [0,1)) for positions with debt and collateral."""
    dec = MARKETS[market]['decimals']
    pos = [p for p in raw['positions'] if p['borrow_usd'] > 0 and int(p['collateral']) > 0]
    coll = np.array([int(p['collateral']) / 10 ** dec for p in pos])
    debt = np.array([p['borrow_usd'] for p in pos])
    cusd = np.array([p['collateral_usd'] for p in pos])
    h = np.array([(int(p['user'][-8:], 16) % 10000) / 10000 for p in pos])  # deterministic per wallet, stable across runs
    return coll, debt, cusd.sum() / coll.sum(), h


def reshape(coll, debt, p_book, p0, lltv, cap):
    """Borrowers draw the same fraction of their allowance under (lltv, cap); debt restated at p0."""
    ltv = np.minimum(debt / (coll * p_book) * cap / 0.75, lltv * 0.99)
    return ltv * coll * p0


def nearest_key(d, pct):
    return d[min(d, key=lambda k: abs(float(k) - pct))]


def capacity(depth, market, lltv, params):
    """USD of collateral absorbable per step at slippage <= lif-1 (nearest measured entry)."""
    pct, prod = 100 * (lif(lltv) - 1), MARKETS[market]['cb_product']
    dex = nearest_key(depth['dex'][market]['capacity_usd_at_slippage'], pct)['usd']
    cex = sum(nearest_key(v[prod]['bid_depth_usd'], pct) for v in depth['cex'].values() if prod in v)
    s = params['scenario']
    if s == 'ABC':
        return np.inf
    return dex * params['k_dex'] + (cex * params['k_cex'] if s == 'AB' else 0)


def simulate(book, path, params):
    """book: (coll_units, debt_usd, hash) arrays. path: market price per step; the oracle lags it by params['lag_bars'].
    Positions are sorted by their initial liquidation price, so at oracle price p everything that can be in the queue or
    the warning zone sits in the prefix [:kw]; debts only fall (repays, partial seizures), so the prefix is a superset and
    LTV is re-checked explicitly inside it. Calm steps cost one searchsorted, crash steps contiguous slice ops.
    Largest-debt-first service scans a static debt-descending index in chunks until the step's capacity is used up.
    Seizure and bad debt are valued at the oracle price (as Morpho does); liquidators sell at market, so a step is
    skipped when LIF * p_mkt / p_oracle <= 1 (no bonus left) and depth is consumed at market value.
    Borrower response: a position is responsive if hash < resp_share. A responsive, alive, un-queued position that has
    spent >= react_min cumulative minutes in the warning zone (lltv - warn_gap < LTV <= lltv) repays once to
    LTV = lltv - 2*warn_gap and can re-trigger if it re-enters the zone. Legacy `cure` (uniform per-step fraction) kept, default 0."""
    coll, debt = book[0].astype(float).copy(), book[1].astype(float).copy()
    lltv, L, base, cure, wg = params['lltv'], lif(params['lltv']), params['base_eff'], params['cure'], params['warn_gap']
    n = len(debt)
    order = np.argsort(-(debt / (coll * lltv)))  # highest liquidation price first
    coll, debt = coll[order], debt[order]
    resp = book[2][order] < params['resp_share']
    react_steps = params['react_min'] / BAR_MIN
    neg_p_liq = -debt / (coll * lltv)
    by_debt = np.argsort(-debt)
    # ponytail: by_debt stays static; a repaid or partially liquidated position keeps its old debt rank.
    alive, entered, warned, liq_step = np.ones(n, bool), np.full(n, -1), np.full(n, -1), np.full(n, -1)
    inq, zone_steps = np.zeros(n, bool), np.zeros(n, int)
    avail, seized_total, realized, cured, max_q, peak_step, unrealized = base, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
    oracle = lagged(path, params['lag_bars'])
    trough, trough_short = int(np.argmin(oracle)), np.zeros(n)
    for t, (p, pm) in enumerate(zip(oracle.tolist(), path.tolist())):
        avail = min(base, avail + params['r'] * base)
        kw = int(np.searchsorted(neg_p_liq, -p * (lltv - wg) / lltv))  # prefix that can be queued or warned
        step_seized, f = 0.0, pm / p  # f converts oracle-valued seizure to market-valued depth consumed
        if kw:
            ltv = debt[:kw] / np.where(coll[:kw] > 0, coll[:kw] * p, 1)
            m = alive[:kw] & (ltv > lltv)
            inq[:kw] = m
            inq[kw:] = False  # a queued position can bounce out of the prefix in one bar; it must not be served while healthy
            e = entered[:kw]
            e[(e < 0) & m] = t
            warn = alive[:kw] & ~m & (ltv > lltv - wg)
            w = warned[:kw]
            w[(w < 0) & warn] = t
            z = zone_steps[:kw]
            z[warn] += 1  # not reset on queue entry: a partially liquidated position dipping back into the zone is cured the same bar
            act = warn & resp[:kw] & (z >= react_steps)
            if act.any():
                d0 = debt[:kw][act]
                new = (lltv - 2 * wg) * coll[:kw][act] * p
                cured += float((d0 - new).sum())
                debt[:kw][act] = new
                z[act] = 0
            if cure:
                cured += cure * float(debt[:kw][warn].sum())
                debt[:kw][warn] *= 1 - cure
            k = int(m.sum())
        else:
            inq[:] = False
            k = 0
        if k:
            q_total = float((np.minimum(debt[:kw] * L, coll[:kw] * p) * m).sum())
            max_q = max(max_q, q_total)
            if L * f <= 1:  # market already below oracle by more than the bonus: no one liquidates at a loss
                pass
            elif avail >= q_total * f:  # everything clears this step; order is irrelevant
                realized += float((np.maximum(0, debt[:kw] - coll[:kw] * p / L) * m).sum())
                liq_step[:kw][m] = t
                alive[:kw] &= ~m
                inq[:kw] = False
                debt[:kw] *= ~m
                coll[:kw] *= ~m
                step_seized = q_total
            else:
                for s0 in range(0, n, 1024):
                    idx = by_debt[s0:s0 + 1024]
                    idx = idx[inq[idx]]
                    if not len(idx):
                        continue
                    seize = np.minimum(debt[idx] * L, coll[idx] * p)
                    cum = np.cumsum(seize)
                    nf = int(np.searchsorted(cum, avail / f - step_seized, side='right'))  # full liquidations that fit
                    full = idx[:nf]
                    realized += float(np.maximum(0, debt[full] - coll[full] * p / L).sum())
                    alive[full], inq[full], liq_step[full] = False, False, t
                    debt[full] = coll[full] = 0
                    step_seized += float(cum[nf - 1]) if nf else 0.0
                    if nf < len(idx):  # partial: seize what is left, then stop serving
                        left = avail / f - step_seized
                        i = int(idx[nf])
                        debt[i] -= left / L
                        coll[i] -= left / p
                        step_seized = avail / f
                        break
            seized_total += step_seized
            avail -= step_seized * f
            peak_step = max(peak_step, step_seized)
        if t == trough:
            trough_short = np.maximum(0, debt - coll * p / L)  # per-position shortfall at the trough; counted only if never liquidated
    done = liq_step >= 0
    unrealized = float(trough_short[~done].sum())
    q = (liq_step[done] - entered[done]) * BAR_MIN
    wt = np.where(warned[done] >= 0, entered[done] - warned[done], 0) * BAR_MIN  # 0 = jumped straight into the queue
    supply = book[1].sum() / 0.9
    return dict(liquidated_usd=float(seized_total), repaid_usd=float(seized_total / L), n_liquidated=int(done.sum()),
                cured_usd=cured, resp_share_debt=float(book[1][book[2] < params['resp_share']].sum() / book[1].sum()),
                realized_bad_debt_usd=realized, unrealized_bad_debt_usd=unrealized,
                bad_debt_pct_supply=float(100 * (realized + unrealized) / supply), max_queue_usd=float(max_q),
                queue_minutes_p50=float(np.percentile(q, 50)) if len(q) else None, queue_minutes_p95=float(np.percentile(q, 95)) if len(q) else None,
                warn_minutes_p50=float(np.percentile(wt, 50)) if len(wt) else None,
                peak_step_liquidated_usd=float(peak_step), steps=len(path))


def lagged(lows, lag):
    return np.concatenate([np.repeat(lows[:1], lag), lows[:len(lows) - lag]]) if lag else lows


def crash_path(candles, p0):
    """Normalized market path from the pre-trough peak: p(t) = p0 * low(t) / peak_high."""
    c = np.array(candles, float)
    trough = int(np.argmin(c[:, 3]))
    peak = int(np.argmax(c[:trough + 1, 2]))
    return p0 * c[peak:, 3] / c[peak, 2]


def real_path(candles, start, end):
    return np.array([r[3] for r in candles if start <= r[0] < end], float)


def run(market, window, book, depth, candles, **kw):
    params = dict(DEFAULTS, **kw)
    coll, debt, p_book, h = book
    if params['reshape']:
        path = crash_path(candles, p_book)
        debt = reshape(coll, debt, p_book, p_book, params['lltv'], params['cap'])
    else:
        path = real_path(candles, params['start'], params['end'])
    params['base_eff'] = capacity(depth, market, params['lltv'], params)
    res = simulate((coll, debt, h), path, params)
    return dict(market=market, window=window, **{k: v for k, v in params.items() if k not in ('base_eff', 'start', 'end')}, **res)


def key(r):
    d = {k: r[k] for k in ('market', 'window', 'lltv', 'cap', 'scenario', 'k_dex', 'k_cex', 'r', 'lag_bars', 'reshape', 'warn_gap', 'resp_share', 'react_min', 'book')}
    d['resp_share'], d['react_min'] = float(d['resp_share']), int(d['react_min'])  # 0 and 0.0 are the same run
    return json.dumps(d, sort_keys=True)


def save(rows, calibrated=None):
    old = load(OUT) if os.path.exists(OUT) else {}
    merged = {key(r): r for r in old.get('runs', [])}
    merged.update((key(r), r) for r in rows)
    out = dict(generated_at=int(time.time()), defaults=DEFAULTS, calibrated=calibrated or old.get('calibrated'), runs=list(merged.values()))
    json.dump(out, open(OUT, 'w'))
    return out


def calibrated():
    """(resp_share, react_min) from a previous `calib` invocation, or None."""
    c = (load(OUT).get('calibrated') or {}) if os.path.exists(OUT) else {}
    return (c['resp_share'], c['react_min']) if 'resp_share' in c else None


def today_book(market):
    return book_arrays(load(os.path.join(DATA, 'positions_%s.json' % market)), market)


def candles_for(market, window):
    return load(os.path.join(DATA, 'prices', '%s_%s.json' % (window, MARKETS[market]['cb_product'])))


def grid(markets, depth, shares, react):
    rows = []
    for m in markets:
        book = today_book(m)
        for w, _, _ in WINDOWS:
            c = candles_for(m, w)
            for sh in shares:
                for lltv in (0.625, 0.70, 0.77, 0.80, 0.86):
                    for cap in (c for c in (0.50, 0.60, 0.70, 0.75) if c < lltv):  # cap >= lltv clips most of the book: meaningless
                        for sc in ('A', 'AB', 'ABC'):
                            rows.append(dict(run(m, w, book, depth, c, lltv=lltv, cap=cap, scenario=sc, resp_share=sh, react_min=react), book='today'))
    return rows


def sensitivity(markets, depth, share, react):
    rows = []
    for m in markets:
        book = today_book(m)
        for w, _, _ in WINDOWS:
            c = candles_for(m, w)
            for kd in (0.1, 0.5, 1.0):
                for kc in (0.1, 0.3, 1.0):
                    for lag in (0, 1, 3):
                        rows.append(dict(run(m, w, book, depth, c, k_dex=kd, k_cex=kc, lag_bars=lag, resp_share=share, react_min=react), book='today'))
            if m == 'cbBTC' and w in ('Mar2020', 'May2021'):
                for sh in sorted({0, share, 0.9}):
                    for d in sorted({15, react, 240}):
                        rows.append(dict(run(m, w, book, depth, c, resp_share=sh, react_min=d), book='today'))
    return rows


def oracle_end(cw, market):
    """Last Chainlink update in the calibration window's oracle file = end of the calibration horizon."""
    f = os.path.join(DATA, 'oracle', '%s_%s.json' % (cw, ORACLE_ASSET[market]))
    return load(f)[-1][0] if os.path.exists(f) else None


def calibration(depth):
    """Sweep (resp_share, react_min) on the lived events (rebuilt books, real paths, AB); pick the pair minimizing the sum
    of squared log(sim/realized) over the three cbBTC events. Returns (rows, calibrated dict or None)."""
    cal_path = os.path.join(DATA, 'calibration.json')
    cal = load(cal_path) if os.path.exists(cal_path) else None
    if cal is None:
        print('data/calibration.json missing: simulated only, (s*, d*) not fitted')
    rows, sims, realized, books = [], {}, {}, {}
    for cw, pw, date, mk in CALIB:
        for m in mk:
            path = os.path.join(DATA, 'book_%s_%s.json' % (m, date))
            if not os.path.exists(path):
                print('%s %s: no rebuilt book at %s, skipped' % (cw, m, path))
                continue
            raw = load(path)
            book, c = book_arrays(raw, m), candles_for(m, pw)
            end = oracle_end(cw, m) or c[-1][0] + 300
            books[cw, m] = (raw, book, c, end)
            realized[cw, m] = ((cal.get('windows', {}).get(cw, {}).get(m, {}).get('volume', {}) or {}).get('repaid_usd')) if cal else None
            pmin = real_path(c, raw['as_of'], end).min()  # frozen-book upper bound: debt with LTV > lltv at the trough
            at_risk = float(book[1][book[1] > MARKETS[m]['lltv'] * book[0] * pmin].sum())
            print('%-8s %-5s book $%.0fM at %.0f; trough %.0f (%+.0f%%): $%.0fM of frozen-book debt crosses lltv; realized repaid %s' % (
                cw, m, book[1].sum() / 1e6, book[2], pmin, 100 * (pmin / book[2] - 1), at_risk / 1e6,
                '$%.1fM' % (realized[cw, m] / 1e6) if realized[cw, m] else 'n/a'))
            for sh in [0] + SHARES:
                for d in (REACTS if sh else [DEFAULTS['react_min']]):
                    for sc in (('A', 'AB', 'ABC') if sh == 0 else ('AB',)):
                        r = dict(run(m, pw, book, depth, c, scenario=sc, resp_share=sh, react_min=d, reshape=False, start=raw['as_of'], end=end),
                                 book=date, calib_window=cw, realized_repaid_usd=realized[cw, m], at_risk_usd_at_trough=at_risk)
                        rows.append(r)
                        if sc == 'AB':
                            sims[cw, m, sh, d] = r
    ratio = lambda cw, m, sh, d: sims[cw, m, sh, d]['repaid_usd'] / realized[cw, m] if realized.get(cw, m) else None
    btc = [(cw, m) for cw, _, _, mk in CALIB for m in mk if m == 'cbBTC' and realized.get(cw, m)]
    eth = [(cw, m) for cw, _, _, mk in CALIB for m in mk if m == 'WETH' and realized.get(cw, m)]
    best = None
    print('\nsimulated / realized repaid, AB, cbBTC (%s); rows react_min, cols resp_share:' % ' / '.join(cw for cw, _ in btc))
    print('%-5s' % 'd\\s' + ''.join('%20s' % ('%.1f (debt %.2f)' % (sh, sims[btc[0][0], 'cbBTC', sh, REACTS[0]]['resp_share_debt']) if btc else sh) for sh in SHARES))
    print('%-5s' % 's=0' + '%20s' % ' / '.join('%.2f' % ratio(cw, m, 0, DEFAULTS['react_min']) for cw, m in btc))
    for d in REACTS:
        cells = []
        for sh in SHARES:
            rs = [ratio(cw, m, sh, d) for cw, m in btc]
            sq = sum(np.log(x) ** 2 if x else np.inf for x in rs) if rs else np.inf
            cells.append(' / '.join('%.2f' % x for x in rs) + ('*' if sq < 0.02 else ' '))
            if rs and (best is None or sq < best[0]):
                best = (sq, sh, d)
        print('%-5d' % d + ''.join('%20s' % c for c in cells))
    out = None
    if best:
        sq, sh, d = best
        ratios = {'%s %s' % (cw, m): ratio(cw, m, sh, d) for cw, m in btc + eth}
        out = dict(resp_share=sh, react_min=d, warn_gap=DEFAULTS['warn_gap'], ratios=ratios, sum_sq_log_cbBTC=sq,
                   resp_share_debt={'%s %s' % (cw, m): sims[cw, m, sh, d]['resp_share_debt'] for cw, m in btc + eth})
        print('(s*, d*) = (%.1f, %d min), sum sq log %.3f: ' % (sh, d, sq) + ', '.join('%s %.2fx' % kv for kv in ratios.items()))
        print('debt-weighted responsive share at s*: ' + ', '.join('%s %.2f' % kv for kv in out['resp_share_debt'].items()))
    return rows, out


def table(rows, share, react):
    dflt = lambda r: (r.get('book') == 'today' and r['k_dex'] == DEFAULTS['k_dex'] and r['k_cex'] == DEFAULTS['k_cex']
                      and r['lag_bars'] == DEFAULTS['lag_bars'] and r['resp_share'] == share and r['react_min'] == react)
    base = [r for r in rows if dflt(r) and r['lltv'] == 0.86 and r['cap'] == 0.75]
    ab = [r for r in rows if dflt(r) and r['scenario'] == 'AB']
    print('\nresp_share %.1f, react_min %d. %-6s %-8s | %-22s | %-22s | %-22s | max lltv with 0 bad debt (AB): cap .75 / any cap' % (
        share, react, 'mkt', 'window', 'A liq / bad $M', 'AB liq / bad $M', 'ABC liq / bad $M'))
    for m in sorted({r['market'] for r in base}):
        for w, _, _ in WINDOWS:
            cells = []
            for sc in ('A', 'AB', 'ABC'):
                r = next((r for r in base if r['market'] == m and r['window'] == w and r['scenario'] == sc), None)
                cells.append('%9.1f / %9.2f' % (r['liquidated_usd'] / 1e6, (r['realized_bad_debt_usd'] + r['unrealized_bad_debt_usd']) / 1e6) if r else ' ' * 22)
            ok = lambda r: r['realized_bad_debt_usd'] + r['unrealized_bad_debt_usd'] == 0
            z75 = [r['lltv'] for r in ab if r['market'] == m and r['window'] == w and r['cap'] == 0.75 and ok(r)]
            zany = [r['lltv'] for r in ab if r['market'] == m and r['window'] == w and ok(r)]
            print('%-6s %-8s | %s | %s | %s | %s / %s' % (m, w, *cells, max(z75) if z75 else 'none', max(zany) if zany else 'none'))
            r = next((r for r in base if r['market'] == m and r['window'] == w and r['scenario'] == 'AB'), None)
            if m == 'cbBTC' and r:
                print('%-6s %-8s   AB: borrowers repaid $%.1fM; median liquidated position had %s min of warning before crossing lltv' % (
                    '', '', r['cured_usd'] / 1e6, '%.0f' % r['warn_minutes_p50'] if r['warn_minutes_p50'] is not None else 'n/a'))


if __name__ == '__main__':
    args = sys.argv[1:]
    markets = [args.pop(args.index('--market') + 1)] if '--market' in args else ['cbBTC', 'WETH']
    share_arg = float(args.pop(args.index('--share') + 1)) if '--share' in args else None  # grid at this share only (to split invocations)
    args = [a for a in args if a not in ('--market', '--share')]
    what = args[0] if args else 'all'
    depth = load(os.path.join(DATA, 'depth.json'))
    t0, rows, cal = time.time(), [], None
    if what in ('calib', 'all'):
        cal_rows, cal = calibration(depth)
        rows += cal_rows
    star = (cal['resp_share'], cal['react_min']) if cal else calibrated()
    if star is None:
        print('no (s*, d*): run `calib` first; grid/sens run at resp_share 0')
        star = (0.0, DEFAULTS['react_min'])
    if what in ('grid', 'all'):
        n = len(rows)
        rows += grid(markets, depth, [share_arg] if share_arg is not None else sorted({0.0, star[0]}), star[1])
        print('grid: %d runs, total %.0fs' % (len(rows) - n, time.time() - t0))
    if what in ('sens', 'all'):
        n = len(rows)
        rows += sensitivity(markets, depth, *star)
        print('sensitivity: %d runs, total %.0fs' % (len(rows) - n, time.time() - t0))
    out = save(rows, cal)
    print('saved %d runs to %s (%.0fs)' % (len(out['runs']), OUT, time.time() - t0))

    book, c = today_book('cbBTC'), candles_for('cbBTC', 'Jun2026')
    r = run('cbBTC', 'Jun2026', book, depth, c, lltv=0.86, cap=0.75, scenario='ABC')
    assert r['realized_bad_debt_usd'] == 0, r
    r2 = run('cbBTC', 'Mar2020', book, depth, candles_for('cbBTC', 'Mar2020'), lltv=0.86, cap=0.75, scenario='A')
    assert r2['unrealized_bad_debt_usd'] > 0, r2
    print('asserts ok (no borrower action): Jun2026 ABC realized bad debt 0 (liquidated $%.1fM); Mar2020 A unrealized bad debt $%.1fM' % (r['liquidated_usd'] / 1e6, r2['unrealized_bad_debt_usd'] / 1e6))
    if star[0]:
        r = run('cbBTC', 'Jun2026', book, depth, c, lltv=0.86, cap=0.75, scenario='ABC', resp_share=star[0], react_min=star[1])
        assert r['realized_bad_debt_usd'] == 0, r
        print('asserts ok (s %.1f, d %d): Jun2026 ABC realized bad debt 0 (liquidated $%.1fM, repaid by borrowers $%.1fM)' % (star[0], star[1], r['liquidated_usd'] / 1e6, r['cured_usd'] / 1e6))
    table(out['runs'], *star)
