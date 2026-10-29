"""Offline what-if: replay a committed rebuilt loan book through a crash path with your own LLTV and liquidator capital. No network, no keys.
Run: .venv/bin/python -m spine.whatif --market cbBTC --book 2026-06-01 --path Mar2020 --lltv 0.80 --capital-multiple 3
     .venv/bin/python -m spine.whatif --list                       valid markets, books and paths
     .venv/bin/python -m spine.whatif --market cbBTC --book 2026-06-01 --bench    time the stress-grid cells on that book
Reads only committed files: data/book_<market>_<date>.json, data/prices/, data/depth.json, data/backtest.json (the fit and stored runs), data/calibration.json.
It never reads data/positions_*.json (gitignored), so it cannot reproduce data/stress_grid.csv, which was run on that live book.
Paths: the seven crash paths (stress_grid.LABEL) rescale the pre-trough peak-to-recovery shape onto the book's price and re-draw the book under your
(LLTV, cap), as stress_grid does. An event path (event:Feb2026, event:Jun2026a, ...) replays the book on the real price path that followed it; the book is
not reshaped, so --cap does not apply. With the defaults an event replay repeats a calibration run stored in data/backtest.json, and says whether it matched.
Two measures are printed on separate lines and never added (definitions in stress_grid.py):
  underwater_unserved_at_trough: shortfall of positions still alive and underwater at the lowest oracle print, plus what was already realized by then.
  realized_loss: shortfall realized on liquidations by the end of the replayed path."""
import glob, math, os, platform, re, statistics, sys, time
import numpy as np
from spine.api import DATA, MARKETS, load
from spine.backtest import CALIB, DEFAULTS, book_arrays, calibrated, candles_for, key, oracle_end, run, saved_runs
from spine.fetch_prices import WINDOWS
from spine.stress_grid import CAPITAL_MULTIPLES, LABEL, LLTV_CAP

COMPARED = ('trough_exposure_usd', 'realized_bad_debt_usd', 'unrealized_bad_debt_usd', 'liquidated_usd')


def fail(msg):
    """Exit with a one-line error on stderr. Bad names get the valid choices in the message."""
    raise SystemExit('error: ' + msg)


def committed_books():
    """{market: [book dates]} from the data/book_<market>_<date>.json files in the repository."""
    out = {}
    for f in sorted(glob.glob(os.path.join(DATA, 'book_*_*.json'))):
        m = re.fullmatch(r'book_(.+)_(\d{4}-\d{2}-\d{2})\.json', os.path.basename(f))
        if m and m[1] in MARKETS:
            out.setdefault(m[1], []).append(m[2])
    return out


def events_for(market, book):
    """{'event:<name>': price window} for the calibration events that replay this market's book. The prefix keeps an event apart from a crash
    path of the same name (Feb2026 and Oct2025 are both)."""
    return {'event:' + cw: pw for cw, pw, date, mk in CALIB if date == book and market in mk}


def crash_paths_for(market):
    return [w for w, _, _ in WINDOWS if candles_for(market, w) is not None]


def paths_for(market, book):
    return crash_paths_for(market) + list(events_for(market, book))


def check_names(market, book, path=None):
    """Exit with an error, listing the valid choices, unless market, book (and path, if given) are all committed."""
    books = committed_books()
    if market not in books:
        fail('unknown market %r. Markets with a committed book: %s.%s' % (
            market, ', '.join(sorted(books)), '' if market not in MARKETS else ' %s is a known market but has no committed book (see spine.rebuild_book).' % market))
    if book not in books[market]:
        fail('no committed book %r for %s. Books: %s.' % (book, market, ', '.join(books[market])))
    if path is not None and path not in paths_for(market, book):
        fail('unknown path %r for %s book %s. Crash paths: %s. Events that replay this book: %s.' % (
            path, market, book, ', '.join(crash_paths_for(market)), ', '.join(events_for(market, book)) or 'none'))


def load_book(market, book):
    raw = load('book_%s_%s' % (market, book))
    return raw, book_arrays(raw, market)


def replay(market, book, path, *, lltv=None, cap=None, multiple=1.0, scenario='AB', resp_share=None, react_min=None, loaded=None, depth=None):
    """One replay of a committed book on `path`. Returns (run result, notes). Defaults: the market's LLTV and max draw, observed liquidator capital,
    the calibrated borrower-response fit. `loaded` = load_book(...) result to reuse."""
    check_names(market, book, path)
    raw, arrays = loaded or load_book(market, book)
    star = calibrated()
    if star is None and (resp_share is None or react_min is None):
        fail('no usable calibrated fit in data/backtest.json; pass both --resp-share and --react-min')
    sh, d, fb = (resp_share if resp_share is not None else star[0]), (react_min if react_min is not None else star[1]), (star[2] if star else DEFAULTS['full_below_usd'])
    lltv, cap = MARKETS[market]['lltv'] if lltv is None else lltv, MARKETS[market]['max_draw'] if cap is None else cap
    kw = dict(lltv=lltv, cap=cap, scenario=scenario, resp_share=sh, react_min=d, full_below_usd=fb, cex_cap_usd=DEFAULTS['cex_cap_usd'] * multiple)
    events = events_for(market, book)
    if path in events:
        window = events[path]
        c = candles_for(market, window)
        kw.update(reshape=False, start=raw['as_of'], end=oracle_end(path[len('event:'):], market) or c[-1][0] + 300)
    else:
        window, c = path, candles_for(market, path)
    res = run(market, window, arrays, depth or load('depth'), c, **kw)
    res['path'], res['is_event'], res['book'] = path, path in events, book
    notes = []
    if not res['is_event'] and cap >= lltv:
        notes.append('cap %.2f >= LLTV %.2f: most of the book is re-drawn at the LLTV clip, so the result says little (the stress grid avoids this)' % (cap, lltv))
    return res, notes


def compare_stored(res):
    """('reproduced' | 'differs' | 'none', detail): the data/backtest.json run with the same parameters, book and window, if there is one."""
    old = {key(r): r for r in saved_runs()}.get(key(res))
    if old is None:
        return 'none', 'no stored run with these parameters, book and path in data/backtest.json (it stores calibration events on committed books and crash paths on the uncommitted live book)'
    if all(math.isclose(res[k], old[k], rel_tol=1e-9, abs_tol=1e-6) for k in COMPARED):
        return 'reproduced', 'matches the stored run in data/backtest.json on %s' % ', '.join(COMPARED)
    return 'differs', 'DIFFERS from the stored run in data/backtest.json: %s. Stored runs used the depth snapshot of the hour they ran in, which is not kept, and these results move with depth.' % (
        '; '.join('%s %.1f vs stored %.1f' % (k, res[k], old[k]) for k in COMPARED if not math.isclose(res[k], old[k], rel_tol=1e-9, abs_tol=1e-6)))


def usd(x):
    return '$%.1fM' % (x / 1e6) if abs(x) >= 1e5 else '$%.0f' % x


def report(res, raw, notes, depth_date):
    debt, cap = raw['borrow_usd_total'], res['cex_cap_usd']
    status, detail = compare_stored(res)
    kind = 'real event path, book not reshaped (cap does not apply)' if res['is_event'] else 'crash path from %s, book re-drawn under the LLTV and cap below' % LABEL.get(res['path'], res['path'])
    lines = ['book:       %s %s, rebuilt %s (%s): %d positions, $%.1fM borrowed, collateral priced at $%.0f' % (
                 res['market'], res['book'], raw['as_of_date'], 'data/book_%s_%s.json' % (res['market'], res['book']), raw['count'], debt / 1e6, raw['price']),
             'path:       %s (%s; %s prices)' % (res['path'], kind, MARKETS[res['market']]['cb_product']),
             'parameters: LLTV %.4g%s, scenario %s, resp_share %.4g, react_min %d, liquidator capital %s per day, depth snapshot %s' % (
                 res['lltv'], '' if res['is_event'] else ', cap %.4g' % res['cap'], res['scenario'], res['resp_share'], res['react_min'],
                 'unlimited' if math.isinf(cap) else '%s (%.4gx the observed %s)' % (usd(cap), cap / DEFAULTS['cex_cap_usd'], usd(DEFAULTS['cex_cap_usd'])), depth_date),
             '',
             'underwater_unserved_at_trough: %s (%.2f%% of book debt)' % (usd(res['trough_exposure_usd']), 100 * res['trough_exposure_usd'] / debt),
             'realized_loss:                 %s (%.2f%% of book debt)' % (usd(res['realized_bad_debt_usd']), 100 * res['realized_bad_debt_usd'] / debt),
             'underwater_at_end:             %s' % usd(res['unrealized_bad_debt_usd']),
             'binds_first:                   %s' % (res['first_bind'] or 'none'),
             '',
             'The two measures are taken at different moments and are not added. Percentages are of the book debt above, not of market supply.',
             'stored-run check: %s: %s' % (status, detail)]
    return '\n'.join(lines + ['note: ' + n for n in notes])


def bench(market, book, repeats=1, paths=None):
    """Time spine.backtest.run (reshape + capacity + simulate) over the stress-grid cells (crash path x LLTV/cap x capital) on a committed book.
    Book and depth loading are outside the timer. Returns a dict of measured seconds."""
    check_names(market, book)
    loaded, depth, star = load_book(market, book), load('depth'), calibrated()
    assert star, 'no usable calibrated fit in data/backtest.json'
    cells = [(w, lltv, cap, mult) for w in (paths or crash_paths_for(market)) for lltv, cap in LLTV_CAP for mult in CAPITAL_MULTIPLES]
    times = []
    for _ in range(repeats):
        for w, lltv, cap, mult in cells:
            c = candles_for(market, w)
            t = time.perf_counter()
            run(market, w, loaded[1], depth, c, lltv=lltv, cap=cap, scenario='AB', resp_share=star[0], react_min=star[1], full_below_usd=star[2], cex_cap_usd=DEFAULTS['cex_cap_usd'] * mult)
            times.append(time.perf_counter() - t)
    n = len(cells)
    return dict(market=market, book=book, positions=loaded[0]['count'], cells=n, repeats=repeats, paths=len(paths or crash_paths_for(market)), total_s=sum(times) / repeats,
                mean_s=statistics.mean(times), median_s=statistics.median(times), min_s=min(times), max_s=max(times),
                python=platform.python_version(), numpy=np.__version__, cpus=os.cpu_count(), platform=platform.platform())


def bench_report(b):
    return '\n'.join(['bench: %d stress-grid cells (%d crash paths x %d LLTV/cap x %d capital levels) on %s book %s (%d positions), %d pass(es)' % (
                          b['cells'], b['paths'], len(LLTV_CAP), len(CAPITAL_MULTIPLES), b['market'], b['book'], b['positions'], b['repeats']),
                      'timed: backtest.run = reshape + capacity + simulate; book and depth loading are not timed',
                      'total per pass %.2f s; per cell mean %.0f ms, median %.0f ms, min %.0f ms, max %.0f ms' % (b['total_s'], 1e3 * b['mean_s'], 1e3 * b['median_s'], 1e3 * b['min_s'], 1e3 * b['max_s']),
                      'python %s, numpy %s, %s logical CPUs, %s' % (b['python'], b['numpy'], b['cpus'], b['platform'])])


def listing():
    lines = ['Committed books (data/book_<market>_<date>.json):']
    for m, dates in committed_books().items():
        for d in dates:
            lines.append('  %s %s: crash paths %s; events %s' % (m, d, ', '.join(crash_paths_for(m)), ', '.join(events_for(m, d)) or 'none'))
    return '\n'.join(lines)


USAGE = """usage: python -m spine.whatif --market M --book DATE --path P [--lltv X] [--cap X] [--capital-multiple X] [--scenario A|AB|ABC] [--resp-share X] [--react-min N]
       python -m spine.whatif --market M --book DATE --bench [--repeats N]
       python -m spine.whatif --list"""
VALUE_FLAGS = ('market', 'book', 'path', 'lltv', 'cap', 'capital-multiple', 'scenario', 'resp-share', 'react-min', 'repeats')


def parse(args):
    """Hand-parsed `--flag value` / `--bench` / `--list` into a dict keyed by flag name with dashes as underscores."""
    out, i = {}, 0
    while i < len(args):
        name = args[i][2:] if args[i].startswith('--') else None
        if name in ('bench', 'list'):
            out[name], i = True, i + 1
        elif name in VALUE_FLAGS and i + 1 < len(args):
            out[name.replace('-', '_')], i = args[i + 1], i + 2
        else:
            fail('unrecognized or incomplete argument %r\n%s' % (args[i], USAGE))
    return out


def number(a, name, lo=None, hi=None, kind=float, lo_ok=False):
    """a[name] as a number, or None if it was not given. Must be above lo (at or above if lo_ok) and below hi."""
    if name not in a:
        return None
    try:
        x = kind(a[name])
    except ValueError:
        fail('--%s needs a number, got %r' % (name.replace('_', '-'), a[name]))
    if (lo is not None and not (x >= lo if lo_ok else x > lo)) or (hi is not None and not x < hi):
        fail('--%s must be %s %s%s, got %s' % (name.replace('_', '-'), 'at least' if lo_ok else 'above', lo, '' if hi is None else ' and below %s' % hi, a[name]))
    return x


def main(args):
    a = parse(args)
    if a.get('list'):
        print(listing())
        return
    if not ('market' in a and 'book' in a and ('path' in a or a.get('bench'))):
        fail('--market, --book and --path are required (--path is not needed with --bench); --list shows the choices\n' + USAGE)
    check_names(a['market'], a['book'], None if a.get('bench') else a['path'])
    if a.get('bench'):
        print(bench_report(bench(a['market'], a['book'], number(a, 'repeats', 0, kind=int) or 1)))
        return
    loaded, depth = load_book(a['market'], a['book']), load('depth')
    multiple = number(a, 'capital_multiple', 0) or 1.0  # float('inf') parses: unlimited capital
    scenario = a.get('scenario', 'AB')
    if scenario not in ('A', 'AB', 'ABC'):
        fail('--scenario must be A, AB or ABC, got %r' % scenario)
    res, notes = replay(a['market'], a['book'], a['path'], lltv=number(a, 'lltv', 0, 1), cap=number(a, 'cap', 0, 1), multiple=multiple, scenario=scenario,
                        resp_share=number(a, 'resp_share', 0, 1.0000001, lo_ok=True), react_min=number(a, 'react_min', 0, kind=int), loaded=loaded, depth=depth)
    print(report(res, loaded[0], notes, depth['fetched_at'][:10]))


if __name__ == '__main__':
    main(sys.argv[1:])
