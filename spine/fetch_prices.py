"""Coinbase Exchange candles for the stress windows -> data/prices/. stdlib only."""
import os, datetime as dt, urllib.error
from spine.api import coinbase_get, load, save, data_path, day_ts

# (name, start, end) inclusive, UTC. backtest.py imports this.
WINDOWS = [
    ('Mar2020', '2020-03-01', '2020-03-20'),
    ('May2021', '2021-05-05', '2021-05-25'),
    ('FTX2022', '2022-11-01', '2022-11-15'),
    ('Aug2024', '2024-07-25', '2024-08-10'),
    ('Oct2025', '2025-10-04', '2025-10-15'),
    ('Feb2026', '2026-01-24', '2026-02-12'),
    ('Jun2026', '2026-05-30', '2026-07-05'),
]
PRODUCTS = ['BTC-USD', 'ETH-USD', 'SOL-USD', 'XRP-USD', 'DOGE-USD', 'ADA-USD', 'LTC-USD']
DAILY_PRODUCTS = ['BTC-USD', 'ETH-USD']
H1, H4, H24 = 3600, 14400, 86400


def iso(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')


def candles(product, gran, start, end):
    """[ts, open, high, low, close] sorted and deduped; [] if the product has no data."""
    out, cur = {}, start
    while cur < end:
        nxt = min(end, cur + gran * 300)
        try:
            rows = coinbase_get(f'/products/{product}/candles', granularity=gran, start=iso(cur), end=iso(nxt))
        except urllib.error.HTTPError as e:
            if e.code == 404:  # product does not exist
                return []
            raise
        for t, lo, hi, op, cl, _ in rows:
            out[t] = [t, op, hi, lo, cl]
        cur = nxt
    return [out[t] for t in sorted(out)]


def fetch_all():
    index = load('prices/index') or {'windows': {}, 'gaps': [], 'daily': {}}
    today = day_ts(dt.date.today().isoformat())
    for name, start, end in WINDOWS:
        end_ts = day_ts(end) + 86400
        for p in PRODUCTS:
            if (os.path.exists(data_path(f'prices/{name}_{p}')) or [name, p] in index['gaps']) and end_ts <= today:
                continue
            rows = candles(p, 300, day_ts(start), end_ts)
            if not rows:
                if [name, p] not in index['gaps']:
                    index['gaps'].append([name, p])
                print(f'{name} {p}: no data, gap recorded')
                continue
            save(f'prices/{name}_{p}', rows)
            index['windows'].setdefault(name, {})[p] = dict(start=start, end=end, candles=len(rows))
            print(f'{name} {p}: {len(rows)} candles')
    for p in DAILY_PRODUCTS:
        rows = candles(p, 86400, day_ts('2020-01-01'), today + 86400)
        save(f'prices/daily_{p}', rows)
        index['daily'][p] = dict(start='2020-01-01', end=dt.date.today().isoformat(), candles=len(rows))
        print(f'daily {p}: {len(rows)} candles')
    index['fetched_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
    save('prices/index', index, indent=1)
    return index


def max_drop(c, span):
    """Worst high-to-low move over any span seconds, same method as research/crash_table.py."""
    m = 0.0
    for i, x in enumerate(c):
        j = i
        while j < len(c) and c[j][0] - x[0] <= span:
            m = max(m, (x[2] - c[j][3]) / x[2])
            j += 1
    return m


def crash_stats(c):
    """c is [ts, o, h, l, c] rows. Returns dict of peak, trough after peak, p2t, worst 1h/4h/24h (fractions)."""
    hi = max(c, key=lambda x: x[2])
    lo = min((x for x in c if x[0] >= hi[0]), key=lambda x: x[3])
    return dict(peak=hi[2], peak_ts=hi[0], trough=lo[3], trough_ts=lo[0], p2t=(hi[2] - lo[3]) / hi[2],
                h1=max_drop(c, H1), h4=max_drop(c, H4), h24=max_drop(c, H24))


if __name__ == '__main__':
    fetch_all()
    stats = {}
    print(f"{'window':8} {'asset':8} {'peak':>10} {'trough':>10} {'p2t':>7} {'1h':>7} {'4h':>7} {'24h':>7}")
    for name, _, _ in WINDOWS:
        for p in DAILY_PRODUCTS:
            s = crash_stats(load(f'prices/{name}_{p}'))
            stats[name, p] = s
            print(f"{name:8} {p:8} {s['peak']:10.0f} {s['trough']:10.0f} {s['p2t']*100:6.1f}% {s['h1']*100:6.1f}% {s['h4']*100:6.1f}% {s['h24']*100:6.1f}%")
    assert 0.57 < stats['Mar2020', 'BTC-USD']['p2t'] < 0.59
    assert 0.49 < stats['Mar2020', 'BTC-USD']['h24'] < 0.51
    assert 0.37 < stats['May2021', 'ETH-USD']['h4'] < 0.39
    print('ok')
