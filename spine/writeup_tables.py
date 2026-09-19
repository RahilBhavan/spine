"""Prints every numeric table in WRITEUP.md as Markdown, cut from data/ so the writeup cannot drift from the data. stdlib only.
Run: python3.12 -m spine.writeup_tables   (reads data/backtest.json, calibration.json, summary.json, depth.json, prices/)"""
from spine.api import load
from spine.fetch_prices import WINDOWS, max_drop, H4, H24

BT, CAL, SUMMARY, DEPTH = load('backtest'), load('calibration'), load('summary'), load('depth')
STAR = BT['calibrated']
D = BT['defaults']
BASE = dict(book=BT['latest_book'], k_dex=D['k_dex'], k_cex=D['k_cex'], r=D['r'], lag_bars=D['lag_bars'], margin=D['margin'], cex_cap_usd=D['cex_cap_usd'],
            beta=D['beta'], seed=0, resp_share=STAR['resp_share'], react_min=STAR['react_min'], close_target=STAR['close_target'], full_below_usd=STAR['full_below_usd'],
            lltv=0.86, cap=0.75, scenario='AB', market='cbBTC')
FIT = 'fitted response s %.1f / d %d min, %s, depth multipliers constant (beta %.2f)' % (STAR['resp_share'], STAR['react_min'], 'bots close in full' if STAR['close_target'] >= 1 else 'bots trim to %.0f%%' % (100 * STAR['close_target']), D['beta'])
BETAS = (0.0, 0.5493061443340549, 1.0986122886681098)
BETA_NOTE = ('Depth per step is k * exp(-beta * |trailing 1h return| / 0.05); beta %.2f is anchored on one Kaiko point (Oct 10 2025: '
             'top-of-book depth down >90%% on a ~10%% hourly move), not fitted.' % D['beta'])
SUPPLY = {m: SUMMARY['markets'][m]['state']['supply_usd'] for m in ('cbBTC', 'WETH')}
LIVED = [('Oct2025', 'Oct 9-12 2025'), ('Feb2026', 'Feb 2-8 2026'), ('Jun2026a', 'Jun 1-7 2026'), ('Jun2026b', 'Jun 23-27 2026')]
LABEL = dict(Mar2020='Mar 2020', May2021='May 2021', FTX2022='FTX Nov 2022', Aug2024='Aug 2024', Oct2025='Oct 2025', Feb2026='Feb 2026', Jun2026='Jun 2026')


def find(**kw):
    f = dict(BASE, **kw)
    hits = [r for r in BT['runs'] if all(r.get(k) == v for k, v in f.items())]
    assert len(hits) == 1, (len(hits), kw)
    return hits[0]


def bad(r):
    return r['realized_bad_debt_usd'] + r['unrealized_bad_debt_usd']


def usd(x):
    return '0' if x == 0 else '$%.2fM' % (x / 1e6) if x < 1e6 else '$%.1fM' % (x / 1e6)


def pct(x, market='cbBTC'):
    return '%.1f%%' % (100 * x / SUPPLY[market])


def bad_pct(r):
    return '0' if bad(r) == 0 else '%s (%s)' % (usd(bad(r)), pct(bad(r), r['market']))


def expo(r):
    """Exposure marked at the trough: realized so far plus every alive position's shortfall at the lowest oracle print."""
    return r['trough_exposure_usd']


def expo_pct(r):
    return '0' if expo(r) == 0 else '%s (%s)' % (usd(expo(r)), pct(expo(r), r['market']))


def both(r):
    """'loss by end of path / exposure at trough'."""
    return '%s / %s' % (bad_pct(r), expo_pct(r))


def dur(minutes):
    if minutes is None:
        return 'n/a'
    if minutes < 120:
        return '%.0f min' % minutes
    if minutes < 48 * 60:
        return '%.0f h' % (minutes / 60)
    return '%.1f days' % (minutes / 1440)


def table(head, rows):
    print('| ' + ' | '.join(head) + ' |')
    print('|' + '---|' * len(head))
    for r in rows:
        print('| ' + ' | '.join(str(c) for c in r) + ' |')
    print()


def recommendation():
    print('## Short version: recommendation row, cbBTC (Mar 2020, AB, %s, cap 75%%)\n' % FIT)
    rows = [('%g%%' % (100 * l), both(find(lltv=l, window='Mar2020'))) for l in (0.86, 0.80, 0.77)]
    for kc in (0.1, 1.0):
        rs = [find(window='Mar2020', k_cex=kc, k_dex=kd, lag_bars=lag) for kd in (0.1, 0.5, 1.0) for lag in (0, 1, 3)]
        rows.append(('86%%, k_cex %.1f' % kc, '%s at k_dex 0.5 / lag 1; %s to %s across k_dex and lag' % (
            bad_pct(find(window='Mar2020', k_cex=kc)), usd(min(map(bad, rs))), usd(max(map(bad, rs))))))
    table(['LLTV', 'Loss by end of path / exposure at trough (% of supply)'], rows)


def lived_events():
    print('## Section 2: lived events (calibration.json, cbBTC)\n')
    rows = []
    for w, label in LIVED:
        c = CAL['windows'][w]['cbBTC']
        v, b, lt, lq = c['volume'], c['bonus'], c['latency'], c['liquidators']
        rows.append((label, '{:,}'.format(v['n']), usd(v['repaid_usd']), usd(v['seized_usd']), '%.2f%%' % (100 * b['p50']),
                     '%ds / %ds' % (lt['p50'], lt['p90']), '%.0f%%' % (100 * lt['within']['60']), lq['distinct'], '%.0f%%' % (100 * lq['top'][0]['share'])))
    table(['Window', 'cbBTC liquidations', 'Repaid', 'Seized', 'Bonus (p50)', 'Latency p50 / p90', 'Within 60s', 'Liquidators', 'Top share'], rows)
    pk = CAL['windows']['Feb2026']['cbBTC']['peaks']
    cex = DEPTH['cex']['coinbase']['BTC-USD']['bid_depth_usd']['4.38']
    dex = DEPTH['dex']['cbBTC']['capacity_usd_at_slippage']['4.38']['usd']
    print('Feb 2026 peak throughput: %s repaid in the busiest 5 minutes, %s in the busiest hour. Coinbase BTC-USD bids within 4.38%%: %s; Base DEX cbBTC->USDC at 4.38%%: %s.\n' % (
        usd(pk['peak_5m']['repaid_usd']), usd(pk['peak_1h']['repaid_usd']), usd(cex), usd(dex)))
    print('Full-liquidation share: ' + ', '.join('%s %.0f%%' % (label, 100 * CAL['windows'][w]['cbBTC']['latency']['full_share']) for w, label in LIVED) + '\n')


def warning_time():
    print('## Section 3: warning time (AB 86/75, %s; median liquidated position)\n' % FIT)
    rows = sorted(((LABEL[w], find(window=w)['warn_minutes_p50']) for w, _, _ in WINDOWS), key=lambda x: -(x[1] or 0))
    table(['Crash', 'Warning time for the median liquidated position'], [(w, dur(m)) for w, m in rows])


def borrower_response():
    s, d = STAR['resp_share'], STAR['react_min']
    for w in ('Mar2020', 'May2021'):
        print('## Section 3: borrower response (%s, AB 86/75, %s)\n' % (LABEL[w], FIT))
        cases = [('None respond', 0.0, d), ('%.0f%% respond within %s (fitted)' % (100 * s, dur(d)), s, d),
                 ('%.0f%% respond within 15 min' % (100 * s), s, 15), ('90% respond within 15 min', 0.9, 15)]
        rows = []
        for label, sh, dm in cases:
            r = find(window=w, resp_share=sh, react_min=dm)
            rows.append((label, usd(r['liquidated_usd']), usd(bad(r))))
        table(['Borrowers', 'Liquidated', 'Bad debt'], rows)


def seven_paths():
    print('## Section 4: seven paths (cbBTC 86/75, %s)\n' % FIT)
    rows = []
    for w, _, _ in WINDOWS:
        c = load('prices/%s_BTC-USD' % w)
        ab, abc = find(window=w), find(window=w, scenario='ABC')
        rows.append((LABEL[w], '-%.0f%% / -%.0f%%' % (100 * max_drop(c, H4), 100 * max_drop(c, H24)), usd(ab['liquidated_usd']), bad_pct(ab), expo_pct(ab),
                     '%s / %s' % (dur(ab['queue_minutes_p50']), dur(ab['queue_minutes_p95'])), both(abc)))
    table(['Path', 'Worst 4h / 24h', 'AB: liquidated', 'AB: loss by end of path', 'AB: exposure at trough', 'AB: queue p50 / p95', 'ABC: loss / exposure'], rows)
    print('Percentages are of the $%.2fB USDC supplied to the market. Loss = shortfall realized on liquidations plus what is still underwater at the end of the path; exposure = the same marked at the lowest oracle print. %s\n' % (SUPPLY['cbBTC'] / 1e9, BETA_NOTE))


def lltv_grid():
    print('## Section 4: LLTV grid (cbBTC, %s; cap 75%%, 60%% where 75%% would exceed the LLTV)\n' % FIT)
    rows = []
    others = [w for w, _, _ in WINDOWS if w not in ('Mar2020', 'May2021')]
    for l in (0.86, 0.80, 0.77, 0.70, 0.625):
        cap = 0.75 if l > 0.75 else 0.60
        lif = min(1.15, 1 / (0.3 * l + 0.7))
        cells = ['%s / %s' % (usd(bad(r)), usd(expo(r))) for r in (find(lltv=l, cap=cap, window=w, scenario=sc) for sc in ('AB', 'ABC') for w in ('Mar2020', 'May2021'))]
        other = max(max(bad(r), expo(r)) for r in (find(lltv=l, cap=cap, window=w, scenario=sc) for sc in ('AB', 'ABC') for w in others))
        rows.append(('%g%%' % (100 * l), '%.1f%%' % (100 / lif), *cells, usd(other)))
    table(['LLTV', 'Bad-debt LTV (1/LIF)', 'AB: Mar 2020', 'AB: May 2021', 'ABC: Mar 2020', 'ABC: May 2021', 'Other five paths (max)'], rows)
    print('Cells are loss by end of path / exposure at trough.\n')


def k_cex_line():
    print('## Section 4: exchange-depth sensitivity (cbBTC 86/75, Mar 2020, AB; k_cex and k_dex are base values, beta %.2f)\n' % D['beta'])
    parts = []
    for kc in (0.1, 0.3, 1.0):
        rs = [bad(find(window='Mar2020', k_cex=kc, k_dex=kd, lag_bars=lag)) for kd in (0.1, 0.5, 1.0) for lag in (0, 1, 3)]
        parts.append('k_cex %.1f: %s (%s) at k_dex 0.5 / lag 1, %s to %s across k_dex and lag' % (
            kc, usd(bad(find(window='Mar2020', k_cex=kc))), pct(bad(find(window='Mar2020', k_cex=kc))), usd(min(rs)), usd(max(rs))))
    print('; '.join(parts) + '.\n')


def beta_table():
    print('## Section 4: depth collapse (cbBTC, AB, cap 75%%, %s). %s\n' % (FIT, BETA_NOTE))
    rows = []
    for w in ('Mar2020', 'May2021'):
        for l in (0.86, 0.80, 0.77):
            rows.append((LABEL[w], '%g%%' % (100 * l), *(both(find(window=w, lltv=l, beta=b)) for b in BETAS)))
    table(['Path', 'LLTV'] + ['beta %.2f%s' % (b, ' (constant depth)' if b == 0 else '') for b in BETAS], rows)
    print('Cells are loss by end of path / exposure at trough.\n')


def seed_table():
    seeds = sorted({r['seed'] for r in BT['runs']})
    print('## Section 4 (j): responsive-wallet assignment (cbBTC, AB, cap 75%%, %s; bad debt over hash seeds %d-%d)\n' % (FIT, seeds[0], seeds[-1]))
    rows = []
    for w in ('Mar2020', 'May2021'):
        for l in (0.86, 0.80, 0.77):
            xs = sorted(bad(find(window=w, lltv=l, seed=s)) for s in seeds)
            rows.append((LABEL[w], '%g%%' % (100 * l), usd(xs[0]), usd(xs[len(xs) // 2]), usd(xs[-1])))
    table(['Path', 'LLTV', 'Bad debt min', 'median', 'max'], rows)


def weth_line():
    print('## Section 4: WETH (cap 75%%, %s; %% of WETH supply $%.0fM)\n' % (FIT, SUPPLY['WETH'] / 1e6))
    rows = []
    for l in (0.86, 0.80, 0.77):
        for sc in ('AB', 'ABC'):
            rows.append(('%g%%' % (100 * l), sc, *(bad_pct(find(market='WETH', lltv=l, window=w, scenario=sc)) for w in ('Mar2020', 'May2021', 'Aug2024')),
                         usd(max(bad(find(market='WETH', lltv=l, window=w, scenario=sc)) for w, _, _ in WINDOWS if w not in ('Mar2020', 'May2021', 'Aug2024')))))
    table(['LLTV', 'Scenario', 'Mar 2020', 'May 2021', 'Aug 2024', 'Other four (max)'], rows)


def capital_range():
    for w in ('Mar2020', 'May2021'):
        print('## Section 4: liquidator capital (cbBTC, %s, AB, cap 75%%, %s; Tier B rolling-24h cap as a multiple of the max collateral seized in one day on the market, $%.1fM from calibration.json via backtest.json defaults)\n' % (LABEL[w], FIT, D['cex_cap_usd'] / 1e6))
        mults = (1, 3, 10, float('inf'))
        rows = [('%g%%' % (100 * l), *(both(find(window=w, lltv=l, cex_cap_usd=D['cex_cap_usd'] * m)) for m in mults)) for l in (0.86, 0.80, 0.77)]
        table(['LLTV', '1x', '3x', '10x', 'depth-limited only'], rows)
        print('Cells are loss by end of path / exposure at trough.\n')


def style_table():
    print('## Section 4: liquidation style (cbBTC, AB, cap 75%%, %s). Full close is what bots do (80-94%% of lived liquidations repaid the whole debt); trim-to-74%% is the alternative\n' % FIT)
    cols = [(1.0, D['cex_cap_usd']), (0.74, D['cex_cap_usd']), (1.0, float('inf')), (0.74, float('inf'))]
    for w in ('Mar2020', 'May2021'):
        rows = [('%s, %g%%' % (LABEL[w], 100 * l), *(both(find(window=w, lltv=l, close_target=ct, cex_cap_usd=cc)) for ct, cc in cols)) for l in (0.86, 0.80, 0.77)]
        table(['Path, LLTV', 'full close, capital 1x', 'trim to 74%, capital 1x', 'full close, unlimited capital', 'trim to 74%, unlimited capital'], rows)


if __name__ == '__main__':
    fs = STAR['full_share']
    print('Calibrated (s*, d*, fb*) = (%.1f, %d min, $%.0fk); ratios: %s\n' % (STAR['resp_share'], STAR['react_min'], STAR['full_below_usd'] / 1e3, ', '.join('%s %.2fx' % kv for kv in STAR['ratios'].items())))
    print('Full-close threshold sweep (simulated full-liquidation share vs observed %.2f): %s\n' % (fs['observed'], ', '.join('below $%s: %.2f' % kv for kv in fs['sweep'].items())))
    recommendation()
    lived_events()
    warning_time()
    borrower_response()
    seven_paths()
    lltv_grid()
    k_cex_line()
    beta_table()
    weth_line()
    capital_range()
    seed_table()
    style_table()
    assert find(window='Mar2020') is find(lltv=0.86, cap=0.75, window='Mar2020', scenario='AB')  # seven-path row is the grid's 86% cell
    assert all(bad(find(window=w, scenario='ABC')) <= bad(find(window=w, scenario='A')) + 1 for w in ('Oct2025', 'Feb2026', 'Jun2026'))
    print('ok')
