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
DEFAULTS = dict(lltv=0.86, cap=0.75, scenario='AB', k_dex=0.5, k_cex=0.3, r=0.2, lag_bars=1, reshape=True)
# calibration books: (window in fetch_oracle/calibrate naming, price window, book date, markets)
CALIB = [('Feb2026', 'Feb2026', '2026-02-03', ['cbBTC', 'WETH']), ('Jun2026a', 'Jun2026', '2026-06-01', ['cbBTC', 'WETH']),
         ('Oct2025', 'Oct2025', '2025-10-09', ['cbBTC'])]
ORACLE_ASSET = {'cbBTC': 'BTC', 'WETH': 'ETH'}


def load(path):
    return json.load(open(path))


def book_arrays(raw, market):
    """(collateral units, debt usd, book price) for positions with debt and collateral."""
    dec = MARKETS[market]['decimals']
    pos = [p for p in raw['positions'] if p['borrow_usd'] > 0 and int(p['collateral']) > 0]
    coll = np.array([int(p['collateral']) / 10 ** dec for p in pos])
    debt = np.array([p['borrow_usd'] for p in pos])
    cusd = np.array([p['collateral_usd'] for p in pos])
    return coll, debt, cusd.sum() / coll.sum()


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
    """book: (coll_units, debt_usd) arrays. path: market price per step; the oracle lags it by params['lag_bars'].
    Positions are sorted by liquidation price, so the queue at oracle price p is the alive prefix [:k] with k = #(p_liq > p):
    calm steps cost one searchsorted, crash steps cost contiguous slice ops. Largest-debt-first service scans a static
    debt-descending index in chunks until the step's capacity is used up. Seizure and bad debt are valued at the oracle
    price (as Morpho does); liquidators sell at market, so a step is skipped when LIF * p_mkt / p_oracle <= 1 (no bonus
    left) and depth is consumed at market value."""
    coll, debt = book[0].astype(float).copy(), book[1].astype(float).copy()
    lltv, L, base = params['lltv'], lif(params['lltv']), params['base_eff']
    n = len(debt)
    order = np.argsort(-(debt / (coll * lltv)))  # highest liquidation price first
    coll, debt = coll[order], debt[order]
    neg_p_liq = -debt / (coll * lltv)
    by_debt = np.argsort(-debt)
    # ponytail: by_debt stays static; a partially liquidated position keeps its old debt rank.
    alive, entered, liq_step = np.ones(n, bool), np.full(n, -1), np.full(n, -1)
    inq, stale = alive.copy(), []  # inq = alive minus partially liquidated ("stale") positions whose LTV dropped back under lltv
    avail, seized_total, realized, max_q, peak_step, unrealized = base, 0.0, 0.0, 0.0, 0.0, 0.0
    oracle = lagged(path, params['lag_bars'])
    trough = int(np.argmin(oracle))
    for t, (p, pm) in enumerate(zip(oracle.tolist(), path.tolist())):
        avail = min(base, avail + params['r'] * base)
        k = int(np.searchsorted(neg_p_liq, -p))  # queue = alive positions in [:k]; liquidated ones have debt = coll = 0
        step_seized, f = 0.0, pm / p  # f converts oracle-valued seizure to market-valued depth consumed
        if k:
            if stale:  # a partial seizure at LTV < 1/LIF lowers LTV, so these can sit in the prefix without being liquidatable
                st = np.array(stale)
                inq[st] = alive[st] & (debt[st] > lltv * coll[st] * p)
            m = inq[:k]
            q_total = float((np.minimum(debt[:k] * L, coll[:k] * p) * m).sum())
            max_q = max(max_q, q_total)
            e = entered[:k]
            e[(e < 0) & m] = t
            if L * f <= 1:  # market already below oracle by more than the bonus: no one liquidates at a loss
                pass
            elif avail >= q_total * f:  # everything clears this step; order is irrelevant
                realized += float((np.maximum(0, debt[:k] - coll[:k] * p / L) * m).sum())
                liq_step[:k][m] = t
                alive[:k] &= ~m
                inq[:k] = False
                debt[:k] *= ~m
                coll[:k] *= ~m
                step_seized = q_total
            else:
                for s0 in range(0, n, 1024):
                    idx = by_debt[s0:s0 + 1024]
                    idx = idx[(idx < k) & inq[idx]]
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
                        if i not in stale:
                            stale.append(i)
                        step_seized = avail / f
                        break
            seized_total += step_seized
            avail -= step_seized * f
            peak_step = max(peak_step, step_seized)
        if t == trough:
            unrealized = float(np.maximum(0, debt[alive] - coll[alive] * p / L).sum())
    done = liq_step >= 0
    q = (liq_step[done] - entered[done]) * BAR_MIN
    supply = book[1].sum() / 0.9
    return dict(liquidated_usd=float(seized_total), repaid_usd=float(seized_total / L), n_liquidated=int(done.sum()),
                realized_bad_debt_usd=realized, unrealized_bad_debt_usd=unrealized,
                bad_debt_pct_supply=float(100 * (realized + unrealized) / supply), max_queue_usd=float(max_q),
                queue_minutes_p50=float(np.percentile(q, 50)) if len(q) else None, queue_minutes_p95=float(np.percentile(q, 95)) if len(q) else None,
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
    coll, debt, p_book = book
    if params['reshape']:
        path = crash_path(candles, p_book)
        debt = reshape(coll, debt, p_book, p_book, params['lltv'], params['cap'])
    else:
        path = real_path(candles, params['start'], params['end'])
    params['base_eff'] = capacity(depth, market, params['lltv'], params)
    res = simulate((coll, debt), path, params)
    return dict(market=market, window=window, **{k: v for k, v in params.items() if k not in ('base_eff', 'start', 'end')}, **res)


def key(r):
    return json.dumps({k: r[k] for k in ('market', 'window', 'lltv', 'cap', 'scenario', 'k_dex', 'k_cex', 'r', 'lag_bars', 'reshape', 'book')}, sort_keys=True)


def save(rows):
    old = load(OUT)['runs'] if os.path.exists(OUT) else []
    merged = {key(r): r for r in old}
    merged.update((key(r), r) for r in rows)
    json.dump(dict(generated_at=int(time.time()), defaults=DEFAULTS, runs=list(merged.values())), open(OUT, 'w'))
    return list(merged.values())


def today_book(market):
    return book_arrays(load(os.path.join(DATA, 'positions_%s.json' % market)), market)


def candles_for(market, window):
    return load(os.path.join(DATA, 'prices', '%s_%s.json' % (window, MARKETS[market]['cb_product'])))


def grid(markets, depth):
    rows = []
    for m in markets:
        book = today_book(m)
        for w, _, _ in WINDOWS:
            c = candles_for(m, w)
            for lltv in (0.625, 0.70, 0.77, 0.80, 0.86):
                for cap in (0.50, 0.60, 0.70, 0.75):
                    for sc in ('A', 'AB', 'ABC'):
                        rows.append(dict(run(m, w, book, depth, c, lltv=lltv, cap=cap, scenario=sc), book='today'))
    return rows


def sensitivity(markets, depth):
    rows = []
    for m in markets:
        book = today_book(m)
        for w, _, _ in WINDOWS:
            c = candles_for(m, w)
            for kd in (0.1, 0.5, 1.0):
                for kc in (0.1, 0.3, 1.0):
                    for lag in (0, 1, 3):
                        rows.append(dict(run(m, w, book, depth, c, k_dex=kd, k_cex=kc, lag_bars=lag), book='today'))
    return rows


def oracle_end(cw, market):
    """Last Chainlink update in the calibration window's oracle file = end of the calibration horizon."""
    f = os.path.join(DATA, 'oracle', '%s_%s.json' % (cw, ORACLE_ASSET[market]))
    return load(f)[-1][0] if os.path.exists(f) else None


def calibration(markets, depth):
    rows, cal = [], load(os.path.join(DATA, 'calibration.json')) if os.path.exists(os.path.join(DATA, 'calibration.json')) else None
    if cal is None:
        print('data/calibration.json missing: simulated only, no realized comparison')
    for cw, pw, date, mk in CALIB:
        for m in mk:
            if m not in markets:
                continue
            path = os.path.join(DATA, 'book_%s_%s.json' % (m, date))
            if not os.path.exists(path):
                print('%s %s: no rebuilt book at %s, skipped' % (cw, m, path))
                continue
            raw = load(path)
            book, c = book_arrays(raw, m), candles_for(m, pw)
            end = oracle_end(cw, m) or c[-1][0] + 300
            realized = ((cal.get('windows', {}).get(cw, {}).get(m, {}).get('volume', {}) or {}).get('repaid_usd')) if cal else None
            pmin = real_path(c, raw['as_of'], end).min()  # frozen-book upper bound: debt with LTV > lltv at the trough
            at_risk = float(book[1][book[1] > MARKETS[m]['lltv'] * book[0] * pmin].sum())
            print('%-8s %-5s book $%.0fM at %.0f; trough %.0f (%+.0f%%): $%.0fM of frozen-book debt crosses lltv' % (
                cw, m, book[1].sum() / 1e6, book[2], pmin, 100 * (pmin / book[2] - 1), at_risk / 1e6))
            for sc in ('A', 'AB', 'ABC'):
                r = dict(run(m, pw, book, depth, c, scenario=sc, reshape=False, start=raw['as_of'], end=end), book=date, calib_window=cw)
                r['realized_repaid_usd'], r['at_risk_usd_at_trough'] = realized, at_risk
                rows.append(r)
                print('%-8s %-5s %-3s simulated repaid $%.1fM (seized $%.1fM, n=%d, bad debt $%.2fM)%s' % (
                    cw, m, sc, r['repaid_usd'] / 1e6, r['liquidated_usd'] / 1e6, r['n_liquidated'], (r['realized_bad_debt_usd'] + r['unrealized_bad_debt_usd']) / 1e6,
                    '  realized repaid $%.1fM (%+.0f%%)' % (realized / 1e6, 100 * (r['repaid_usd'] / realized - 1)) if realized else ''))
    return rows


def table(rows):
    base = [r for r in rows if r.get('book') == 'today' and r['lltv'] == 0.86 and r['cap'] == 0.75 and r['k_dex'] == DEFAULTS['k_dex']
            and r['k_cex'] == DEFAULTS['k_cex'] and r['lag_bars'] == DEFAULTS['lag_bars']]
    ab = [r for r in rows if r.get('book') == 'today' and r['scenario'] == 'AB' and r['k_dex'] == DEFAULTS['k_dex'] and r['k_cex'] == DEFAULTS['k_cex']
          and r['lag_bars'] == DEFAULTS['lag_bars']]
    print('\n%-6s %-8s | %-22s | %-22s | %-22s | max lltv with 0 bad debt (AB): cap .75 / any cap' % ('mkt', 'window', 'A liq / bad $M', 'AB liq / bad $M', 'ABC liq / bad $M'))
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


if __name__ == '__main__':
    args = sys.argv[1:]
    markets = [args.pop(args.index('--market') + 1)] if '--market' in args else ['cbBTC', 'WETH']
    args = [a for a in args if a != '--market']
    what = args[0] if args else 'all'
    depth = load(os.path.join(DATA, 'depth.json'))
    t0, rows = time.time(), []
    if what in ('grid', 'all'):
        rows += grid(markets, depth)
        print('grid: %d runs in %.0fs' % (len(rows), time.time() - t0))
    if what in ('sens', 'all'):
        n = len(rows)
        rows += sensitivity(markets, depth)
        print('sensitivity: %d runs, total %.0fs' % (len(rows) - n, time.time() - t0))
    if what in ('calib', 'all'):
        rows += calibration(markets, depth)
    allrows = save(rows)
    print('saved %d runs to %s (%.0fs)' % (len(allrows), OUT, time.time() - t0))

    book, c = today_book('cbBTC'), candles_for('cbBTC', 'Jun2026')
    r = run('cbBTC', 'Jun2026', book, depth, c, lltv=0.86, cap=0.75, scenario='ABC')
    assert r['realized_bad_debt_usd'] == 0, r
    r2 = run('cbBTC', 'Mar2020', book, depth, candles_for('cbBTC', 'Mar2020'), lltv=0.86, cap=0.75, scenario='A')
    assert r2['unrealized_bad_debt_usd'] > 0, r2
    print('asserts ok: Jun2026 ABC realized bad debt 0 (liquidated $%.1fM); Mar2020 A unrealized bad debt $%.1fM' % (r['liquidated_usd'] / 1e6, r2['unrealized_bad_debt_usd'] / 1e6))
    table(allrows)
