"""Prints every numeric table in WRITEUP.md as Markdown, cut from data/ so the writeup cannot drift from the data. stdlib only.
Run: python3.12 -m spine.writeup_tables   (reads data/backtest.json, calibration.json, summary.json, depth.json, prices/)"""
from spine.api import load
from spine.fetch_prices import WINDOWS, max_drop, H4, H24

BT, CAL, SUMMARY, DEPTH = load('backtest'), load('calibration'), load('summary'), load('depth')
STAR = BT['calibrated']
D = BT['defaults']
BASE = dict(book='today', k_dex=D['k_dex'], k_cex=D['k_cex'], r=D['r'], lag_bars=D['lag_bars'], margin=D['margin'], cex_cap_usd=D['cex_cap_usd'],
            resp_share=STAR['resp_share'], react_min=STAR['react_min'], lltv=0.86, cap=0.75, scenario='AB', market='cbBTC')
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
    print('## Short version: recommendation row, cbBTC (Mar 2020, AB, fitted response, cap 75%)\n')
    rows = [('%g%%' % (100 * l), bad_pct(find(lltv=l, window='Mar2020'))) for l in (0.86, 0.80, 0.77)]
    for kc in (0.1, 1.0):
        rs = [find(window='Mar2020', k_cex=kc, k_dex=kd, lag_bars=lag) for kd in (0.1, 0.5, 1.0) for lag in (0, 1, 3)]
        rows.append(('86%%, k_cex %.1f' % kc, '%s at k_dex 0.5 / lag 1; %s to %s across k_dex and lag' % (
            bad_pct(find(window='Mar2020', k_cex=kc)), usd(min(map(bad, rs))), usd(max(map(bad, rs))))))
    table(['LLTV', 'Bad debt (% of supply)'], rows)


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
    print('## Section 3: warning time (AB 86/75, fitted response; median liquidated position)\n')
    rows = sorted(((LABEL[w], find(window=w)['warn_minutes_p50']) for w, _, _ in WINDOWS), key=lambda x: -(x[1] or 0))
    table(['Crash', 'Warning time for the median liquidated position'], [(w, dur(m)) for w, m in rows])


def borrower_response():
    s, d = STAR['resp_share'], STAR['react_min']
    for w in ('Mar2020', 'May2021'):
        print('## Section 3: borrower response (%s, AB 86/75)\n' % LABEL[w])
        cases = [('None respond', 0.0, d), ('%.0f%% respond within %s (fitted)' % (100 * s, dur(d)), s, d),
                 ('%.0f%% respond within 15 min' % (100 * s), s, 15), ('90% respond within 15 min', 0.9, 15)]
        rows = []
        for label, sh, dm in cases:
            r = find(window=w, resp_share=sh, react_min=dm)
            rows.append((label, usd(r['liquidated_usd']), usd(bad(r))))
        table(['Borrowers', 'Liquidated', 'Bad debt'], rows)


def seven_paths():
    print('## Section 4: seven paths (cbBTC 86/75, fitted response)\n')
    rows = []
    for w, _, _ in WINDOWS:
        c = load('prices/%s_BTC-USD' % w)
        ab, abc = find(window=w), find(window=w, scenario='ABC')
        rows.append((LABEL[w], '-%.0f%% / -%.0f%%' % (100 * max_drop(c, H4), 100 * max_drop(c, H24)), usd(ab['liquidated_usd']), bad_pct(ab),
                     '%s / %s' % (dur(ab['queue_minutes_p50']), dur(ab['queue_minutes_p95'])), bad_pct(abc)))
    table(['Path', 'Worst 4h / 24h', 'AB: liquidated', 'AB: bad debt', 'AB: queue p50 / p95', 'ABC: bad debt'], rows)
    print('Percentages are of the $%.2fB USDC supplied to the market.\n' % (SUPPLY['cbBTC'] / 1e9))


def lltv_grid():
    print('## Section 4: LLTV grid (cbBTC, fitted response; cap 75%, 60% where 75% would exceed the LLTV)\n')
    rows = []
    others = [w for w, _, _ in WINDOWS if w not in ('Mar2020', 'May2021')]
    for l in (0.86, 0.80, 0.77, 0.70, 0.625):
        cap = 0.75 if l > 0.75 else 0.60
        lif = min(1.15, 1 / (0.3 * l + 0.7))
        cells = [usd(bad(find(lltv=l, cap=cap, window=w, scenario=sc))) for sc in ('AB', 'ABC') for w in ('Mar2020', 'May2021')]
        other = max(bad(find(lltv=l, cap=cap, window=w, scenario=sc)) for sc in ('AB', 'ABC') for w in others)
        rows.append(('%g%%' % (100 * l), '%.1f%%' % (100 / lif), *cells, usd(other)))
    table(['LLTV', 'Bad-debt LTV (1/LIF)', 'AB: Mar 2020', 'AB: May 2021', 'ABC: Mar 2020', 'ABC: May 2021', 'Other five paths (max)'], rows)


def k_cex_line():
    print('## Section 4: exchange-depth sensitivity (cbBTC 86/75, Mar 2020, AB)\n')
    parts = []
    for kc in (0.1, 0.3, 1.0):
        rs = [bad(find(window='Mar2020', k_cex=kc, k_dex=kd, lag_bars=lag)) for kd in (0.1, 0.5, 1.0) for lag in (0, 1, 3)]
        parts.append('k_cex %.1f: %s (%s) at k_dex 0.5 / lag 1, %s to %s across k_dex and lag' % (
            kc, usd(bad(find(window='Mar2020', k_cex=kc))), pct(bad(find(window='Mar2020', k_cex=kc))), usd(min(rs)), usd(max(rs))))
    print('; '.join(parts) + '.\n')


def weth_line():
    print('## Section 4: WETH (cap 75%%, fitted response; %% of WETH supply $%.0fM)\n' % (SUPPLY['WETH'] / 1e6))
    rows = []
    for l in (0.86, 0.80, 0.77):
        for sc in ('AB', 'ABC'):
            rows.append(('%g%%' % (100 * l), sc, *(bad_pct(find(market='WETH', lltv=l, window=w, scenario=sc)) for w in ('Mar2020', 'May2021', 'Aug2024')),
                         usd(max(bad(find(market='WETH', lltv=l, window=w, scenario=sc)) for w, _, _ in WINDOWS if w not in ('Mar2020', 'May2021', 'Aug2024')))))
    table(['LLTV', 'Scenario', 'Mar 2020', 'May 2021', 'Aug 2024', 'Other four (max)'], rows)


def capital_range():
    for w in ('Mar2020', 'May2021'):
        print('## Section 4: liquidator capital (cbBTC, %s, AB, cap 75%%, fitted response; Tier B rolling-24h cap as a multiple of the max collateral seized in one day on the market, $%.1fM from calibration.json via backtest.json defaults)\n' % (LABEL[w], D['cex_cap_usd'] / 1e6))
        mults = (1, 3, 10, float('inf'))
        rows = [('%g%%' % (100 * l), *(bad_pct(find(window=w, lltv=l, cex_cap_usd=D['cex_cap_usd'] * m)) for m in mults)) for l in (0.86, 0.80, 0.77)]
        table(['LLTV', '1x', '3x', '10x', 'depth-limited only'], rows)


if __name__ == '__main__':
    print('Calibrated (s*, d*) = (%.1f, %d min); ratios: %s\n' % (STAR['resp_share'], STAR['react_min'], ', '.join('%s %.2fx' % kv for kv in STAR['ratios'].items())))
    recommendation()
    lived_events()
    warning_time()
    borrower_response()
    seven_paths()
    lltv_grid()
    k_cex_line()
    weth_line()
    capital_range()
    assert find(window='Mar2020') is find(lltv=0.86, cap=0.75, window='Mar2020', scenario='AB')  # seven-path row is the grid's 86% cell
    assert all(bad(find(window=w, scenario='ABC')) <= bad(find(window=w, scenario='A')) + 1 for w in ('Oct2025', 'Feb2026', 'Jun2026'))
    print('ok')
