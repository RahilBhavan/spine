"""Liquidation-queue backtest (PLAN.md section 4) -> data/backtest.json. numpy; run with .venv/bin/python.
Run: .venv/bin/python -m spine.backtest [grid|sens|calib|all] [--market cbBTC] [--share 0.7] [--max-seconds N] [--check]
Results append to data/backtest.json keyed on parameters; runs already there are skipped, so every mode is incremental.
Past the budget (default 200 s) it saves, prints "partial, rerun to continue" and exits 0; "complete" when nothing is left."""
import json, math, sys, time, datetime, collections
import numpy as np
from spine.api import MARKETS, lif, load, save as save_json, data_path, budget, argv_max_seconds, row_ts
from spine.fetch_prices import WINDOWS

OUT = data_path('backtest')
BAR_MIN = 5
DAY_STEPS = 24 * 60 // BAR_MIN


def cex_cap_default():
    """Max single-UTC-day collateral seized on cbBTC across the calibration windows (Feb 5 2026): the observed ceiling on Tier B
    inventory. Seized (market value of collateral), not repaid, because that is what the ring charges against the cap.
    Rounded to $0.1M so the value is stable across calibration reruns: it is part of every run key."""
    days = [d['seized_usd'] for w in (load('calibration') or {'windows': {}})['windows'].values() for d in w.get('cbBTC', {}).get('daily', {}).values()]
    return round(max(days), -5) if days else 101.1e6


# beta: k_cex(t) = k_cex * exp(-beta * |r_1h| / 0.05); ln(3)/2 makes a 10% hourly move cut depth to a third (0.3 -> 0.1).
# ponytail: one anchor point (Kaiko, Oct 10 2025: top-of-book depth down >90%); FTX ("about half") would pin the curve's shape.
DEFAULTS = dict(lltv=0.86, cap=0.75, scenario='AB', k_dex=0.5, k_cex=0.3, r=0.2, lag_bars=1, reshape=True,
                warn_gap=0.06, resp_share=0.0, react_min=60, cure=0.0, margin=0.01, cex_cap_usd=cex_cap_default(),
                close_target=1.0, full_below_usd=0.0, beta=0.0, seed=0, hold_bars=0, book_multiple=1.0)
SHARES, REACTS = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9], [15, 30, 60, 120, 240]
FULL_BELOW, BETAS = (0.0, 1e3, 2.5e3, 5e3, 1e4, 2.5e4, 5e4), (0.0, math.log(3) / 2, math.log(3))  # beta: none, the Kaiko anchor, twice it
HOUR_BARS, SEEDS = 60 // BAR_MIN, range(10)
CAP_MULTIPLES = (1, 3, 10, np.inf)
# calibration books: (window in fetch_oracle/calibrate naming, price window, book date, markets)
CALIB = [('Feb2026', 'Feb2026', '2026-02-03', ['cbBTC', 'WETH']), ('Jun2026a', 'Jun2026', '2026-06-01', ['cbBTC', 'WETH']),
         ('Oct2025', 'Oct2025', '2025-10-09', ['cbBTC'])]


def book_arrays(raw, market, seed=0):
    """(collateral units, debt usd, book price, responsiveness hash in [0,1)) for positions with debt and collateral.
    seed reshuffles which wallets are responsive; seed 0 is the plain wallet hash."""
    dec = MARKETS[market]['decimals']
    pos = [p for p in raw['positions'] if p['borrow_usd'] > 0 and int(p['collateral']) > 0]
    coll = np.array([int(p['collateral']) / 10 ** dec for p in pos])
    debt = np.array([p['borrow_usd'] for p in pos])
    cusd = np.array([p['collateral_usd'] for p in pos])
    h = np.array([((int(p['user'][-8:], 16) ^ (seed * 0x9E3779B1)) % 10000) / 10000 for p in pos])  # deterministic per wallet and seed
    return coll, debt, cusd.sum() / coll.sum(), h


def reshape(coll, debt, p_book, p0, lltv, cap, max_draw):
    """Borrowers draw the same fraction of their allowance under (lltv, cap) as they do under the product's max_draw today;
    debt restated at p0."""
    ltv = np.minimum(debt / (coll * p_book) * cap / max_draw, lltv * 0.99)
    return ltv * coll * p0


def interp(table, pct):
    """Linear interpolation of a {slippage_pct: usd} table at pct, clamped to the measured range."""
    xs = sorted((float(k), float(v)) for k, v in table.items())
    return float(np.interp(pct, [x for x, _ in xs], [y for _, y in xs]))


def capacity(depth, market, lltv, params):
    """(Tier A, Tier B) USD of collateral absorbable per step at slippage <= lif-1-margin (gas and oracle slack)."""
    pct, prod = 100 * (lif(lltv) - 1 - params['margin']), MARKETS[market]['cb_product']
    dex_tab = depth['dex'].get(market)  # alts have no venue on Base: CEX only
    dex = interp({k: v['usd'] for k, v in dex_tab['capacity_usd_at_slippage'].items()}, pct) if dex_tab else 0.0
    cex = sum(interp(v[prod]['bid_depth_usd'], pct) for v in depth['cex'].values() if prod in v)
    s = params['scenario']
    if s == 'ABC':
        return np.inf, 0.0
    return dex * params['k_dex'], cex * params['k_cex'] if s == 'AB' else 0.0


def events(debt, coll, p, L, tau, fb):
    """Per-position (repay, closes in full, seizure at oracle price p, underwater) for the liquidation rule in simulate()'s docstring."""
    under = debt * L > coll * p
    rep = debt if tau >= 1 else np.clip((debt - tau * coll * p) / (1 - tau * L), 0, debt)  # repay to target LTV; clip to the whole debt
    full_ev = under | (rep >= debt * (1 - 1e-9)) | (debt <= fb)  # small positions are closed outright (gas)
    rep = np.where(full_ev, debt, rep)
    return rep, full_ev, np.where(under, coll * p, rep * L), under


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
    LTV = lltv - 2*warn_gap and can re-trigger if it re-enters the zone. Legacy `cure` (uniform per-step fraction) kept, default 0.
    Capacity is two replenishing pools, Tier A (DEX) and Tier B (CEX-hedged); A is consumed first. Tier B is capital-limited:
    its depth consumed over the trailing 24h (a ring of DAY_STEPS) cannot exceed cex_cap_usd, so it contributes zero at the cap.
    Both pools shrink with the path: base * exp(-beta * |trailing 1h market return| / 0.05) (see DEFAULTS).
    A liquidation event repays just enough to bring the position back to close_target LTV (bots size to what restores health,
    not to zero): r = (debt - target*coll*p) / (1 - target*LIF); it is a full close when r >= debt or the position is underwater
    (debt * LIF > coll * p). close_target >= 1 means always close in full. Partially served positions re-enter the queue if
    still over lltv. full_share = events that closed the position / events."""
    coll, debt = book[0].astype(float).copy(), book[1].astype(float).copy()
    lltv, L, (base_a, base_b), cure, wg = params['lltv'], lif(params['lltv']), params['base_eff'], params['cure'], params['warn_gap']
    cap_b, tau, fb = params['cex_cap_usd'], params['close_target'], params['full_below_usd']
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
    avail_a, avail_b, seized_total, realized, cured, max_q, peak_step, unrealized = base_a, base_b, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
    ring, used_b = np.zeros(DAY_STEPS), 0.0  # Tier B depth consumed per step, trailing 24h
    oracle = lagged(path, params['lag_bars'])
    trough, trough_expo = int(np.argmin(oracle)), 0.0
    g = np.exp(-params['beta'] * np.abs(path / lagged(path, min(HOUR_BARS, len(path))) - 1) / 0.05)  # depth multiplier
    n_events = n_full = 0
    for t, (p, pm, gt) in enumerate(zip(oracle.tolist(), path.tolist(), g.tolist())):
        used_b -= ring[t % DAY_STEPS]  # step t - DAY_STEPS rolls off before this step's cap check: the window is exactly DAY_STEPS bars
        ring[t % DAY_STEPS] = 0.0
        ba, bb = base_a * gt, base_b * gt
        avail_a = min(ba, avail_a + params['r'] * ba)
        avail_b = min(bb, avail_b + params['r'] * bb, max(0.0, cap_b - used_b))
        avail, ub = avail_a + avail_b, 0.0
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
            rep, full_ev, sz, under = events(debt[:kw], coll[:kw], p, L, tau, fb)
            q_total = float((sz * m).sum())
            max_q = max(max_q, float((np.minimum(debt[:kw] * L, coll[:kw] * p) * m).sum()))
            if L * f <= 1:  # market already below oracle by more than the bonus: no one liquidates at a loss
                pass
            elif avail >= q_total * f:  # everything clears this step; order is irrelevant
                close = m & full_ev
                part = m & ~close
                realized += float((np.maximum(0, debt[:kw] - coll[:kw] * p / L) * close).sum())
                n_events, n_full = n_events + k, n_full + int(close.sum())
                liq_step[:kw][close] = t
                alive[:kw] &= ~close
                inq[:kw] = False
                debt[:kw] -= np.where(part, sz / L, 0)
                coll[:kw] -= np.where(part, sz / p, 0)
                debt[:kw] *= ~close
                coll[:kw] *= ~close
                step_seized = q_total
            else:
                for s0 in range(0, n, 1024):
                    idx = by_debt[s0:s0 + 1024]
                    idx = idx[inq[idx]]
                    if not len(idx):
                        continue
                    rep, full_ev, seize, under = events(debt[idx], coll[idx], p, L, tau, fb)
                    cum = np.cumsum(seize)
                    nf = int(np.searchsorted(cum, avail / f - step_seized, side='right'))  # events that fit whole
                    close = full_ev[:nf]
                    fc, fp = idx[:nf][close], idx[:nf][~close]
                    realized += float(np.maximum(0, debt[fc] - coll[fc] * p / L).sum())
                    alive[fc], inq[fc], liq_step[fc] = False, False, t
                    debt[fc] = coll[fc] = 0
                    debt[fp] -= seize[:nf][~close] / L
                    coll[fp] -= seize[:nf][~close] / p
                    inq[fp] = False  # served this step; re-queued next step if still over lltv
                    n_events, n_full = n_events + nf, n_full + int(close.sum())
                    step_seized += float(cum[nf - 1]) if nf else 0.0
                    if nf < len(idx):  # capacity cuts the next event: seize what is left, then stop serving
                        left = avail / f - step_seized
                        i = int(idx[nf])
                        debt[i] -= left / L
                        coll[i] -= left / p
                        n_events += left > 0
                        step_seized = avail / f
                        break
            seized_total += step_seized
            ua = min(step_seized * f, avail_a)
            ub = max(0.0, step_seized * f - ua)
            avail_a, avail_b = avail_a - ua, avail_b - ub
            peak_step = max(peak_step, step_seized)
        used_b += ub
        ring[t % DAY_STEPS] = ub
        if t == trough:  # exposure marked at the trough: everything alive and underwater, plus what was already realized
            trough_expo = float(np.maximum(0, debt - coll * p / L).sum()) + realized
    done = liq_step >= 0
    unrealized = float(np.maximum(0, debt[alive] - coll[alive] * p / L).sum())  # still underwater at the end of the path
    q = (liq_step[done] - entered[done]) * BAR_MIN
    wt = np.where(warned[done] >= 0, entered[done] - warned[done], 0) * BAR_MIN  # 0 = jumped straight into the queue
    supply = book[1].sum() / 0.9
    return dict(liquidated_usd=float(seized_total), repaid_usd=float(seized_total / L), n_liquidated=int(done.sum()),
                n_events=int(n_events), full_share=n_full / n_events if n_events else None, cured_usd=cured, resp_share_debt=float(book[1][book[2] < params['resp_share']].sum() / book[1].sum()),
                realized_bad_debt_usd=realized, unrealized_bad_debt_usd=unrealized, trough_exposure_usd=trough_expo,
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
        if params['hold_bars']:  # hold the trough low for hold_bars before the bounce; calibration (real_path) runs never hold
            i = int(np.argmin(path))
            path = np.concatenate([path[:i + 1], np.full(params['hold_bars'], path[i]), path[i + 1:]])
        coll, debt = coll * params['book_multiple'], debt * params['book_multiple']  # a bigger book with the same LTV distribution: size, not leverage
        debt = reshape(coll, debt, p_book, p_book, params['lltv'], params['cap'], MARKETS[market]['max_draw'])
    else:
        path = real_path(candles, params['start'], params['end'])
    params['base_eff'] = capacity(depth, market, params['lltv'], params)
    res = simulate((coll, debt, h), path, params)
    return dict(market=market, window=window, **{k: v for k, v in params.items() if k not in ('base_eff', 'start', 'end')}, **res)


def key(r):
    d = {k: r[k] for k in ('market', 'window', 'lltv', 'cap', 'scenario', 'k_dex', 'k_cex', 'r', 'lag_bars', 'reshape', 'warn_gap', 'resp_share', 'react_min',
                            'margin', 'cex_cap_usd', 'close_target', 'full_below_usd', 'beta', 'seed', 'book', 'hold_bars', 'book_multiple')}
    d['resp_share'], d['react_min'] = float(d['resp_share']), int(d['react_min'])  # 0 and 0.0 are the same run
    d['close_target'], d['full_below_usd'], d['beta'], d['seed'] = float(d['close_target']), float(d['full_below_usd']), float(d['beta']), int(d['seed'])
    d['hold_bars'], d['book_multiple'] = int(d['hold_bars']), float(d['book_multiple'])
    return json.dumps(d, sort_keys=True)


def save(rows, calibrated=None):
    """Merge rows into data/backtest.json. Live rows (no calib_window) carry the book date as `book`; latest_book is the label
    with the most rows (ties to the newest), so readers see a complete grid while a new date fills in over several cron runs.
    Live rows under any label other than latest_book or the newest are dropped."""
    old = load('backtest') or {}
    merged = {key(r): r for r in saved_runs(old)}
    merged.update((key(r), r) for r in rows)
    live = collections.Counter(r['book'] for r in merged.values() if 'calib_window' not in r)
    latest = max(live, key=lambda b: (live[b], b)) if live else None
    runs = [r for r in merged.values() if 'calib_window' in r or r['book'] in (latest, max(live))]
    out = dict(generated_at=int(time.time()), latest_book=latest, defaults=DEFAULTS, calibrated=calibrated or old.get('calibrated'), runs=runs)
    save_json('backtest', out)
    return out


def saved_runs(out=None):
    """Rows on disk, with params added since they were run filled in at the defaults they ran at."""
    return [dict(DEFAULTS, **r) for r in (out if out is not None else load('backtest') or {}).get('runs', [])]


def calibrated():
    """(resp_share, react_min, full_below_usd) from a previous `calib` invocation, or None if there is none or it was fitted
    under other defaults (margin, cex_cap_usd, beta, close_target): a stale fit must not be paired silently with a new model."""
    c = (load('backtest') or {}).get('calibrated') or {}
    if 'full_below_usd' not in c:
        return None
    stale = {k: (c.get(k), DEFAULTS[k]) for k in ('margin', 'cex_cap_usd', 'beta', 'close_target') if c.get(k) != DEFAULTS[k]}
    if stale:
        print('stored (s*, d*, fb*) was fitted under other defaults (stored, now): %s' % stale)
        return None
    return c['resp_share'], c['react_min'], c['full_below_usd']


def today_book(market, seed=0):
    """(book arrays, label): the label is the positions file's fetch date (UTC), the `book` key of every live grid row."""
    raw = load('positions_%s' % market)
    return book_arrays(raw, market, seed), datetime.datetime.fromtimestamp(raw['fetched_at'], datetime.UTC).date().isoformat()


def candles_for(market, window):
    return load('prices/%s_%s' % (window, MARKETS[market]['cb_product']))


def runner(done, within_budget, new):
    """get(market, window, book, depth, candles, extra, **kw): the saved row if its key is in `done`, else run it, record it in
    `done` and `new`. Raises TimeoutError past the budget instead of starting another run (checked between runs only)."""
    def get(market, window, book, depth, candles, extra, **kw):
        k = key(dict(DEFAULTS, market=market, window=window, **extra, **kw))
        if k in done:
            return done[k]
        if not within_budget():
            raise TimeoutError
        done[k] = r = dict(run(market, window, book, depth, candles, **kw), **extra)
        new.append(r)
        return r
    return get


def grid(markets, depth, shares, react, cf, get):
    for m in markets:
        book, label = today_book(m)
        for w, _, _ in WINDOWS:
            c = candles_for(m, w)
            if c is None:  # no price file for this product in this window (SOL predates May 2021)
                continue
            for sh in shares:
                for lltv in ((0.625, 0.70) if MARKETS[m]['lltv'] < 0.7 else (0.625, 0.70, 0.77, 0.80, 0.86)):
                    for cap in (c for c in (0.50, 0.55, 0.60, 0.70, 0.75) if c < lltv):  # cap >= lltv clips most of the book: meaningless
                        for sc in ('A', 'AB', 'ABC'):
                            if sc == 'A' and m not in depth['dex']:  # no venue on Base: Tier A capacity is (0, 0), the row is junk
                                continue
                            get(m, w, book, depth, c, dict(book=label), lltv=lltv, cap=cap, scenario=sc, resp_share=sh, react_min=react, full_below_usd=cf)


def sensitivity(markets, depth, share, react, cf, get):
    star = dict(resp_share=share, react_min=react, full_below_usd=cf)
    for m in markets:
        book, label = today_book(m)
        own = dict(lltv=MARKETS[m]['lltv'], cap=0.75 if MARKETS[m]['lltv'] > 0.75 else 0.55)  # the market's live terms, not cbBTC's
        for w, _, _ in WINDOWS:
            c = candles_for(m, w)
            if c is None:
                continue
            for kd in (0.1, 0.5, 1.0):
                for kc in (0.1, 0.3, 1.0):
                    for lag in (0, 1, 3):
                        get(m, w, book, depth, c, dict(book=label), k_dex=kd, k_cex=kc, lag_bars=lag, **own, **star)
            if m == 'cbBTC' and w in ('Mar2020', 'May2021'):
                for sh in sorted({0, 0.6, share, 0.9}):
                    for d in sorted({15, 60, react, 240}):
                        get(m, w, book, depth, c, dict(book=label), resp_share=sh, react_min=d, full_below_usd=cf)
                for lltv in (0.86, 0.80, 0.77):  # liquidator capital: observed max day, multiples, and depth-limited only
                    for mult in CAP_MULTIPLES:
                        get(m, w, book, depth, c, dict(book=label), lltv=lltv, cex_cap_usd=DEFAULTS['cex_cap_usd'] * mult, **star)
                    for beta in BETAS:  # depth collapse: none, the Kaiko anchor, twice it
                        get(m, w, book, depth, c, dict(book=label), lltv=lltv, beta=beta, **star)
                    for mult in (1, np.inf):  # liquidation style: bots trim to 74% instead of closing in full
                        get(m, w, book, depth, c, dict(book=label), lltv=lltv, close_target=0.74, cex_cap_usd=DEFAULTS['cex_cap_usd'] * mult, **star)
                    for hb in (12, 288):  # held at the low: one hour, one day before the bounce
                        for sc in ('AB', 'ABC'):
                            get(m, w, book, depth, c, dict(book=label), lltv=lltv, scenario=sc, hold_bars=hb, **star)
                for seed in SEEDS:  # which wallets are responsive: hash seed
                    bs, _ = today_book(m, seed)
                    for lltv in (0.86, 0.80, 0.77):
                        get(m, w, bs, depth, c, dict(book=label), lltv=lltv, seed=seed, **star)
            if m in ('cbXRP', 'SOL') and w == 'Oct2025':  # book size: the multiple of today's debt at which the alt first loses
                for mult in (1, 2, 4, 8, 16, 32):
                    get(m, w, book, depth, c, dict(book=label), lltv=0.625, cap=0.55, scenario='AB', book_multiple=float(mult), **star)


def oracle_end(cw, market):
    """Last Chainlink update in the calibration window's oracle file = end of the calibration horizon."""
    rows = load('oracle/%s_%s' % (cw, MARKETS[market]['feed']))
    return row_ts(rows[-1]) if rows else None


def calibration(depth, get):
    """Lived events (rebuilt books, real paths, AB). First pick full_below_usd fb* whose simulated full-liquidation share (three
    cbBTC events, s 0.7, d 120) is closest to the observed full_share from calibration.json; then sweep (resp_share, react_min)
    at c* and pick the pair minimizing the sum of squared log(sim/realized) over the three cbBTC events. Returns the
    calibrated dict or None."""
    cal = load('calibration')
    if cal is None:
        print('data/calibration.json missing: simulated only, (s*, d*, c*) not fitted')
    sims, realized, books = {}, {}, {}
    for cw, pw, date, mk in CALIB:
        for m in mk:
            raw = load('book_%s_%s' % (m, date))
            if raw is None:
                print('%s %s: no rebuilt book at %s, skipped' % (cw, m, data_path('book_%s_%s' % (m, date))))
                continue
            book, c = book_arrays(raw, m), candles_for(m, pw)
            end = oracle_end(cw, m) or c[-1][0] + 300
            realized[cw, m] = ((cal.get('windows', {}).get(cw, {}).get(m, {}).get('volume', {}) or {}).get('repaid_usd')) if cal else None
            pmin = real_path(c, raw['as_of'], end).min()  # frozen-book upper bound: debt with LTV > lltv at the trough
            at_risk = float(book[1][book[1] > MARKETS[m]['lltv'] * book[0] * pmin].sum())
            extra = dict(book=date, calib_window=cw, realized_repaid_usd=realized[cw, m], at_risk_usd_at_trough=at_risk)
            books[cw, m] = lambda extra=extra, args=(m, pw, book, depth, c), raw=raw, end=end, **kw: get(*args, extra, reshape=False, start=raw['as_of'], end=end, **kw)
            print('%-8s %-5s book $%.0fM at %.0f; trough %.0f (%+.0f%%): $%.0fM of frozen-book debt crosses lltv; realized repaid %s' % (
                cw, m, book[1].sum() / 1e6, book[2], pmin, 100 * (pmin / book[2] - 1), at_risk / 1e6,
                '$%.1fM' % (realized[cw, m] / 1e6) if realized[cw, m] else 'n/a'))
    btc = [(cw, m) for cw, _, _, mk in CALIB for m in mk if m == 'cbBTC' and realized.get(cw, m)]
    eth = [(cw, m) for cw, _, _, mk in CALIB for m in mk if m == 'WETH' and realized.get(cw, m)]
    obs = [cal['windows'][cw]['cbBTC']['latency']['full_share'] for cw, _ in btc] if cal else []
    obs_full, cf_star, sim_full = (sum(obs) / len(obs), DEFAULTS['full_below_usd'], {}) if obs else (None, DEFAULTS['full_below_usd'], {})
    if obs and DEFAULTS['close_target'] < 1:
        print('\nfull-liquidation share, AB, s 0.7, d 120, cbBTC (%s); observed mean %.2f:' % (' / '.join(cw for cw, _ in btc), obs_full))
        for cf in FULL_BELOW:
            fs = [books[cw, m](scenario='AB', resp_share=0.7, react_min=120, full_below_usd=cf)['full_share'] or 0.0 for cw, m in btc]
            sim_full[cf] = sum(fs) / len(fs)
            print('full below $%.0f: %s -> mean %.2f' % (cf, ' / '.join('%.2f' % x for x in fs), sim_full[cf]))
        cf_star = min(sim_full, key=lambda cf: abs(sim_full[cf] - obs_full))
        print('full_below* = $%.0f (simulated %.2f vs observed %.2f)' % (cf_star, sim_full[cf_star], obs_full))
    for (cw, m), run_at in books.items():
        for sh in [0] + SHARES:
            for d in (REACTS if sh else [DEFAULTS['react_min']]):
                for sc in (('A', 'AB', 'ABC') if sh == 0 else ('AB',)):
                    r = run_at(scenario=sc, resp_share=sh, react_min=d, full_below_usd=cf_star)
                    if sc == 'AB':
                        sims[cw, m, sh, d] = r
    ratio = lambda cw, m, sh, d: sims[cw, m, sh, d]['repaid_usd'] / realized[cw, m] if realized.get(cw, m) else None
    best = None
    print('\nsimulated / realized repaid, AB, full below $%.0f, cbBTC (%s); rows react_min, cols resp_share:' % (cf_star, ' / '.join(cw for cw, _ in btc)))
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
        out = dict(resp_share=sh, react_min=d, full_below_usd=cf_star, close_target=DEFAULTS['close_target'], warn_gap=DEFAULTS['warn_gap'], margin=DEFAULTS['margin'],
                   cex_cap_usd=DEFAULTS['cex_cap_usd'], beta=DEFAULTS['beta'], ratios=ratios, sum_sq_log_cbBTC=sq,
                   full_share=dict(observed=obs_full, simulated=sim_full.get(cf_star), sweep=sim_full),
                   resp_share_debt={'%s %s' % (cw, m): sims[cw, m, sh, d]['resp_share_debt'] for cw, m in btc + eth})
        print('(s*, d*, fb*) = (%.1f, %d min, $%.0f), sum sq log %.3f: ' % (sh, d, cf_star, sq) + ', '.join('%s %.2fx' % kv for kv in ratios.items()))
        print('debt-weighted responsive share at s*: ' + ', '.join('%s %.2f' % kv for kv in out['resp_share_debt'].items()))
    return out


def table(out, share, react, cf):
    rows, latest = out['runs'], out['latest_book']
    dflt = lambda r: (r.get('book') == latest and all(r[k] == DEFAULTS[k] for k in ('k_dex', 'k_cex', 'lag_bars', 'beta', 'seed', 'cex_cap_usd', 'hold_bars', 'book_multiple'))
                      and r['resp_share'] == share and r['react_min'] == react and r['full_below_usd'] == cf)
    base = [r for r in rows if dflt(r) and r['lltv'] == 0.86 and r['cap'] == 0.75]
    ab = [r for r in rows if dflt(r) and r['scenario'] == 'AB']
    print('\nresp_share %.1f, react_min %d, full_below_usd %.0f. %-6s %-8s | %-22s | %-22s | %-22s | max lltv with 0 bad debt (AB): cap .75 / any cap' % (
        share, react, cf, 'mkt', 'window', 'A liq / bad $M', 'AB liq / bad $M', 'ABC liq / bad $M'))
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
    max_seconds, args, check = argv_max_seconds()  # --check: level asserts too (paste in the PR); the cron omits it
    markets = [args.pop(args.index('--market') + 1)] if '--market' in args else ['cbBTC', 'WETH']
    share_arg = float(args.pop(args.index('--share') + 1)) if '--share' in args else None  # grid at this share only (to split invocations)
    args = [a for a in args if a not in ('--market', '--share')]
    what = args[0] if args else 'all'
    depth = load('depth')
    t0, cal, star, partial = time.time(), None, None, False
    done = {key(r): r for r in saved_runs()}
    new = []
    get = runner(done, budget(max_seconds), new)
    try:
        if what in ('calib', 'all'):
            cal = calibration(depth, get)
        star = (cal['resp_share'], cal['react_min'], cal['full_below_usd']) if cal else calibrated()
        if star is None:
            print('no (s*, d*, fb*): run `calib` first; grid/sens run at resp_share 0, full_below_usd %.0f' % DEFAULTS['full_below_usd'])
            star = (0.0, DEFAULTS['react_min'], DEFAULTS['full_below_usd'])
        if what in ('grid', 'all'):
            n = len(new)
            grid(markets, depth, [share_arg] if share_arg is not None else sorted({0.0, star[0]}), star[1], star[2], get)
            print('grid: %d new runs, total %.0fs' % (len(new) - n, time.time() - t0))
        if what in ('sens', 'all'):
            n = len(new)
            sensitivity(markets, depth, *star, get)
            print('sensitivity: %d new runs, total %.0fs' % (len(new) - n, time.time() - t0))
    except TimeoutError:
        partial = True
    out = save(new, cal)
    print('saved %d new runs (%d total) to %s (%.0fs)' % (len(new), len(out['runs']), OUT, time.time() - t0))
    if partial:
        print('partial, rerun to continue')
        sys.exit(0)
    print('complete')
    if cal:
        print('calib ratios at (s*, d*, c*): ' + ', '.join('%s %.2fx' % kv for kv in cal['ratios'].items()))
        off = {k: v for k, v in cal['ratios'].items() if 'cbBTC' in k and abs(v - 1) > 0.25}
        assert not off, 'cbBTC lived events off by more than 25%%: %s' % off

    (book, _), c = today_book('cbBTC'), candles_for('cbBTC', 'Jun2026')
    lvl = 'asserts ok' if check else 'level, not asserted without --check'
    for sc in ('AB', 'ABC'):
        r = run('cbBTC', 'Jun2026', book, depth, c, lltv=0.86, cap=0.75, scenario=sc)
        assert not check or r['realized_bad_debt_usd'] == 0, r
        print('%s (no borrower action): Jun2026 %s realized bad debt $%.0f (liquidated $%.1fM)' % (lvl, sc, r['realized_bad_debt_usd'], r['liquidated_usd'] / 1e6))
    r2 = run('cbBTC', 'Mar2020', book, depth, candles_for('cbBTC', 'Mar2020'), lltv=0.86, cap=0.75, scenario='A')
    assert not check or r2['trough_exposure_usd'] > 0, r2
    print('%s (no borrower action): Mar2020 A exposure at trough $%.1fM' % (lvl, r2['trough_exposure_usd'] / 1e6))
    # Tier B ring: no Tier A, cap = one step of Tier B, three positions each seizing exactly 1.0 at p=1 from step 1 on.
    # One clears per rolling 24h: steps 1, 289, 577 (a 578-step path fits all three, a 577-step path only two).
    syn = (np.ones(3), np.ones(3), np.full(3, 0.5))
    ps = dict(DEFAULTS, base_eff=(0.0, 1.0), cex_cap_usd=1.0, r=1.0, lag_bars=0, beta=0.0)
    for steps, want in ((578, 3), (577, 2), (290, 2), (289, 1)):
        s = simulate(syn, np.array([10.0] + [1.0] * (steps - 1)), ps)
        assert s['n_liquidated'] == want, (steps, s['n_liquidated'])
    assert s['queue_minutes_p50'] == 0 and simulate(syn, np.array([10.0] + [1.0] * 577), ps)['queue_minutes_p50'] == DAY_STEPS * BAR_MIN
    print('asserts ok: Tier B cap window is exactly %d bars' % DAY_STEPS)
    if star[0]:
        for sc in ('AB', 'ABC'):
            r = run('cbBTC', 'Jun2026', book, depth, c, lltv=0.86, cap=0.75, scenario=sc, resp_share=star[0], react_min=star[1], full_below_usd=star[2])
            assert not check or r['realized_bad_debt_usd'] == 0, r
            print('%s (s %.1f, d %d, c %.2f): Jun2026 %s realized bad debt $%.0f (liquidated $%.1fM, repaid by borrowers $%.1fM)' % (
                lvl, star[0], star[1], star[2], sc, r['realized_bad_debt_usd'], r['liquidated_usd'] / 1e6, r['cured_usd'] / 1e6))
    table(out, *star)
