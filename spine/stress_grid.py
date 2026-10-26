"""Stress grid: the cbBTC book replayed on every crash path across LLTV x liquidator-capital cells -> data/stress_grid.csv.
Run: .venv/bin/python -m spine.stress_grid [--table] [--check]
Needs data/positions_cbBTC.json (the live book; its fetch date labels every row), depth.json, prices/ and a stored `calib` fit in backtest.json.
--table [Mar2020,May2021,...] prints the Markdown summary from the saved CSV instead of re-running (default: every path with a nonzero cell).
Two measures stay in separate columns and are never added or ranked against each other:
  underwater_unserved_at_trough: shortfall of every position still alive and underwater at the lowest oracle print, plus what was
    already realized by then (backtest.py trough_exposure_usd). It is what the book is exposed to if the price does not bounce.
  realized_loss: shortfall realized on liquidations by the end of the replayed path (backtest.py realized_bad_debt_usd).
binds_first: the limit at the first step with a queue the step could not serve in full (see backtest.simulate)."""
import csv, math, os, sys
from spine.api import DATA, load
from spine.backtest import DEFAULTS, calibrated, candles_for, run, saved_runs, key, today_book
from spine.fetch_prices import WINDOWS

OUT = os.path.join(DATA, 'stress_grid.csv')
MARKET = 'cbBTC'
LLTV_CAP = ((0.86, 0.75), (0.80, 0.75), (0.77, 0.75), (0.70, 0.60))  # cap 60% where 75% would reach the LLTV, as in WRITEUP section 4
CAPITAL_MULTIPLES = (0.5, 1, 3, 10, math.inf)  # of the observed max seized in one day (DEFAULTS cex_cap_usd); inf = depth-limited only
LABEL = dict(Mar2020='Mar 2020', May2021='May 2021', FTX2022='FTX Nov 2022', Aug2024='Aug 2024', Oct2025='Oct 2025', Feb2026='Feb 2026', Jun2026='Jun 2026')
COLUMNS = ['book_date', 'depth_date', 'market', 'crash_path', 'lltv', 'cap', 'scenario', 'liquidator_capital_usd_per_day', 'capital_multiple',
           'resp_share', 'react_min', 'supply_usd',
           'underwater_unserved_at_trough_usd', 'underwater_unserved_at_trough_pct_supply',
           'realized_loss_usd', 'realized_loss_pct_supply', 'underwater_at_end_usd',
           'binds_first', 'binds_first_hour', 'capital_cap_binds_hour']
BIND_LABEL = dict(depth='depth', capital='capital', oracle_gap='oracle gap', none='none')


def hours(step):
    return None if step is None or step < 0 else step * 5 / 60  # BAR_MIN = 5


def row_of(res, *, book_date, depth_date, supply, mult):
    """One CSV row from a backtest.run() result. Unserved exposure and realized loss are copied as they are, never combined."""
    cap = res['cex_cap_usd']
    return dict(book_date=book_date, depth_date=depth_date, market=res['market'], crash_path=res['window'], lltv=res['lltv'], cap=res['cap'],
                scenario=res['scenario'], liquidator_capital_usd_per_day='unlimited' if math.isinf(cap) else round(cap), capital_multiple='unlimited' if math.isinf(mult) else mult,
                resp_share=res['resp_share'], react_min=res['react_min'], supply_usd=round(supply),
                underwater_unserved_at_trough_usd=round(res['trough_exposure_usd'], 2), underwater_unserved_at_trough_pct_supply=round(100 * res['trough_exposure_usd'] / supply, 3),
                realized_loss_usd=round(res['realized_bad_debt_usd'], 2), realized_loss_pct_supply=round(100 * res['realized_bad_debt_usd'] / supply, 3),
                underwater_at_end_usd=round(res['unrealized_bad_debt_usd'], 2),
                binds_first=res['first_bind'] or 'none', binds_first_hour=hours(res['first_bind_step']), capital_cap_binds_hour=hours(res['capital_bind_step']))


def cell(book, depth, candles, window, lltv, cap, mult, star, *, book_date, depth_date, supply, scenario='AB'):
    """Replay one (path, LLTV, capital) cell. star = the calibrated (resp_share, react_min, full_below_usd)."""
    sh, d, fb = star
    res = run(MARKET, window, book, depth, candles, lltv=lltv, cap=cap, scenario=scenario, resp_share=sh, react_min=d, full_below_usd=fb,
              cex_cap_usd=DEFAULTS['cex_cap_usd'] * mult)
    return row_of(res, book_date=book_date, depth_date=depth_date, supply=supply, mult=mult), res


def stored_match(res, book_date, stored):
    """The saved backtest.json run with the same parameters and book label as this replay, or None."""
    return stored.get(key(dict(res, book=book_date)))


def reproduce(book, depth, star, *, book_date, depth_date, supply, stored):
    """March 2020 at 86% / 75%, AB, observed capital: the headline cell of WRITEUP section 4. Returns (row, status). The replay runs twice and
    must agree with itself exactly; it is then compared with the data/backtest.json run for the same book date, if there is one. A stored run
    used the depth snapshot of the hour it ran in, which is not kept, so a difference is reported, not asserted."""
    c = candles_for(MARKET, 'Mar2020')
    row, res = cell(book, depth, c, 'Mar2020', 0.86, 0.75, 1, star, book_date=book_date, depth_date=depth_date, supply=supply)
    assert cell(book, depth, c, 'Mar2020', 0.86, 0.75, 1, star, book_date=book_date, depth_date=depth_date, supply=supply)[0] == row, 'replay is not deterministic'
    old = stored_match(res, book_date, stored)
    if old is None:
        return row, 'no stored run for book %s in data/backtest.json (labels there: %s): not compared with a stored run' % (book_date, ', '.join(sorted({r['book'] for r in stored.values() if 'calib_window' not in r})))
    ks = ('trough_exposure_usd', 'realized_bad_debt_usd', 'unrealized_bad_debt_usd', 'liquidated_usd')
    if all(math.isclose(res[k], old[k], rel_tol=1e-9, abs_tol=1e-6) for k in ks):
        return row, 'reproduced the stored run for book %s' % book_date
    return row, 'DIFFERS from the stored run for book %s: %s (stored ran under that hour\'s depth snapshot)' % (book_date, ', '.join('%s %.1f vs %.1f' % (k, res[k], old[k]) for k in ks))


def grid(book, depth, star, *, book_date, depth_date, supply):
    return [cell(book, depth, candles_for(MARKET, w), w, lltv, cap, mult, star, book_date=book_date, depth_date=depth_date, supply=supply)[0]
            for w, _, _ in WINDOWS for lltv, cap in LLTV_CAP for mult in CAPITAL_MULTIPLES]


def write_csv(rows, path=OUT):
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, COLUMNS, lineterminator='\n')
        w.writeheader()
        w.writerows({k: '' if r[k] is None else r[k] for k in COLUMNS} for r in rows)


def read_csv(path=OUT):
    with open(path) as f:
        return list(csv.DictReader(f))


def usd(x):
    x = float(x)
    return '0' if x == 0 else '$%.2fM' % (x / 1e6) if x < 1e6 else '$%.1fM' % (x / 1e6)


def cap_label(r):
    return 'unlimited' if r['capital_multiple'] == 'unlimited' else '$%.1fM (%gx)' % (float(r['liquidator_capital_usd_per_day']) / 1e6, float(r['capital_multiple']))


def measure(r, usd_col, pct_col):
    return '0' if float(r[usd_col]) == 0 else '%s (%.1f%%)' % (usd(r[usd_col]), float(r[pct_col]))


def binds(r):
    h = r['binds_first_hour']
    first = BIND_LABEL[r['binds_first']] + (' at %.1f h' % float(h) if h else '')
    c = r['capital_cap_binds_hour']
    return first + ('; capital cap from %.1f h' % float(c) if c else '')


def table(rows, paths):
    """Markdown rows for the given crash paths, one per CSV row: book date, path, LLTV, capital, then the two measures in their own columns."""
    out = ['| Book date | Crash path | LLTV / cap | Liquidator capital per day | Underwater and unserved at trough | Realized loss | Binds first |', '|---|---|---|---|---|---|---|']
    for r in rows:
        if r['crash_path'] in paths:
            out.append('| %s | %s | %g%% / %g%% | %s | %s | %s | %s |' % (r['book_date'], LABEL[r['crash_path']], 100 * float(r['lltv']), 100 * float(r['cap']), cap_label(r),
                                                                      measure(r, 'underwater_unserved_at_trough_usd', 'underwater_unserved_at_trough_pct_supply'),
                                                                      measure(r, 'realized_loss_usd', 'realized_loss_pct_supply'), binds(r)))
    return '\n'.join(out)


def clean_paths(rows):
    """Paths where every cell has zero on both measures."""
    return [w for w, _, _ in WINDOWS if all(float(r['underwater_unserved_at_trough_usd']) == 0 and float(r['realized_loss_usd']) == 0 for r in rows if r['crash_path'] == w)]


if __name__ == '__main__':
    args = sys.argv[1:]
    if '--table' in args:
        rows = read_csv()
        i = args.index('--table') + 1
        print(table(rows, args[i].split(',') if i < len(args) else [w for w, _, _ in WINDOWS if w not in clean_paths(rows)]))
        sys.exit(0)
    star, depth = calibrated(), load('depth')
    assert star, 'no stored calibration fit in data/backtest.json (run `python -m spine.backtest calib` first)'
    book, book_date = today_book(MARKET)
    raw = load('positions_%s' % MARKET)
    supply, depth_date = raw['market_state']['supplyAssetsUsd'], depth['fetched_at'][:10]
    print('book %s (%d positions, supply $%.0fM), depth snapshot %s, fit (resp_share, react_min, full_below_usd) = %s' % (book_date, len(book[1]), supply / 1e6, depth_date, star))
    base, status = reproduce(book, depth, star, book_date=book_date, depth_date=depth_date, supply=supply, stored={key(r): r for r in saved_runs()})
    print('baseline Mar 2020 / 86%% / observed capital: underwater and unserved at trough $%.1fM (%.1f%% of supply); realized loss $%.1fM (%.1f%%)' % (
        base['underwater_unserved_at_trough_usd'] / 1e6, base['underwater_unserved_at_trough_pct_supply'], base['realized_loss_usd'] / 1e6, base['realized_loss_pct_supply']))
    print(status)
    rows = grid(book, depth, star, book_date=book_date, depth_date=depth_date, supply=supply)
    own = next(r for r in rows if r['crash_path'] == 'Mar2020' and r['lltv'] == 0.86 and r['capital_multiple'] == 1)
    assert own == base, (own, base)  # the grid's own baseline cell is the reproduced one
    write_csv(rows)
    print('%d cells saved to %s' % (len(rows), OUT))
    if '--check' in args:
        assert len(rows) == len(WINDOWS) * len(LLTV_CAP) * len(CAPITAL_MULTIPLES) and len({(r['crash_path'], r['lltv'], r['capital_multiple']) for r in rows}) == len(rows)
        assert all(r['book_date'] == book_date for r in rows)
        print('asserts ok')
