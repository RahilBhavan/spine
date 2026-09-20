"""Chainlink deviation/heartbeat replay: how far and how late the Base BTC/USD and ETH/USD feeds ran behind Coinbase 5-minute
candles in each stress window -> data/oracle_lag.json as {window: {asset: stats}}. stdlib only.
Run: .venv/bin/python -m spine.oracle_lag   (reads data/oracle/, data/prices/, data/windows.json)"""
import bisect, datetime
from spine.api import load, save, day_ts, row_ts, row_price

WINDOWS = {k: tuple(v) for k, v in load('windows').items()}
ASSETS = ('BTC', 'ETH')
NEAR_LOW = 1.005  # an oracle print within 0.5% of the candle low counts as having reached it
KEYS = ('n_updates', 'interval_s', 'deviation', 'low', 'oracle_low', 'oracle_low_gap_pct', 'lag_to_low_s')


def pctl(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))]  # ponytail: nearest rank, no interpolation


def summary(xs):
    return dict(p50=pctl(xs, 0.5), p90=pctl(xs, 0.9), max=max(xs))


def stats(oracle, candles, t0, t1):
    """Oracle rows [ts, block, price] against candles [ts, o, h, l, c], both restricted to [t0, t1)."""
    rows = [r for r in oracle if t0 <= row_ts(r) < t1]
    cs = [c for c in candles if t0 <= c[0] < t1]
    starts = [c[0] for c in cs]
    close_at = lambda ts: cs[bisect.bisect_right(starts, ts) - 1][4]  # close of the candle containing ts
    dev = [abs(row_price(r) - close_at(row_ts(r))) / close_at(row_ts(r)) for r in rows if row_ts(r) >= starts[0]]
    low = min(cs, key=lambda c: c[3])
    olow = min(rows, key=row_price)
    hit = next((row_ts(r) for r in rows if row_ts(r) >= low[0] and row_price(r) <= low[3] * NEAR_LOW), None)
    return dict(n_updates=len(rows), interval_s=summary([b[0] - a[0] for a, b in zip(rows, rows[1:])]), deviation=summary(dev),
                low=dict(price=low[3], ts=low[0]), oracle_low=dict(price=row_price(olow), ts=row_ts(olow)),
                oracle_low_gap_pct=row_price(olow) / low[3] - 1, lag_to_low_s=None if hit is None else hit - low[0])


def run():
    out = dict(generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'))
    for w, (a, b) in WINDOWS.items():
        for asset in ASSETS:
            oracle, candles = load('oracle/%s_%s' % (w, asset)), load('prices/%s_%s-USD' % (w.rstrip('ab'), asset))
            if oracle and candles:
                out.setdefault(w, {})[asset] = stats(oracle, candles, day_ts(a), day_ts(b) + 86400)
    return out


if __name__ == '__main__':
    out = run()
    save('oracle_lag', out, indent=1)
    for w, assets in out.items():
        for asset, s in (assets.items() if isinstance(assets, dict) else ()):
            print('%-8s %s n=%5d interval p50/p90/max %4d/%4d/%5ds  dev p50/p90/max %.3f%%/%.3f%%/%.3f%%  oracle low vs candle low %+.2f%%  lag %ss' % (
                w, asset, s['n_updates'], s['interval_s']['p50'], s['interval_s']['p90'], s['interval_s']['max'],
                100 * s['deviation']['p50'], 100 * s['deviation']['p90'], 100 * s['deviation']['max'], 100 * s['oracle_low_gap_pct'], 'n/a' if s['lag_to_low_s'] is None else s['lag_to_low_s']))
            assert s['deviation']['p50'] < 0.01 and abs(s['oracle_low_gap_pct']) < 0.02, (w, asset)
    cs = [[t, 100, 101, 100 - i, 100 - i] for i, t in enumerate(range(0, 3000, 300))]  # closes fall 1/bar and close at the low
    syn = stats([[c[0], 0, c[4]] for c in cs], cs, 0, 3000)
    assert syn['deviation']['max'] == 0 and syn['lag_to_low_s'] == 0 and syn['oracle_low_gap_pct'] == 0, syn
    print('ok')
