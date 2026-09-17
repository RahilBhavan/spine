"""Chainlink AnswerUpdated path on Base for BTC/USD and ETH/USD in each stress window
-> data/oracle/<window>_<asset>.json as sorted [[updatedAt, block, price], ...].
Window start is padded by 24h so calibrate.py can find the crossing for early liquidations.
Run: python3.12 -m spine.fetch_oracle [--max-seconds N]. Partial log ranges checkpoint to data/cache/;
when the time budget runs out it exits 0 and says so; rerun until it prints "complete"."""
import os, sys, time
from spine.api import rpc, load, save, data_path, day_ts, budget, argv_max_seconds, row_price

PROXY = {'BTC': '0x64c911996D3c6aC71f9b455B1E8E7266BcbD848F', 'ETH': '0x71041dddad3595F9CEd3DcCFBe3D1F4b0a16Bb70'}
ANSWER_UPDATED = '0x0559884fd3a460db3073b7fc896cc77986f16e378210ded43186175bf646fc5f'
# (first day, last day) inclusive, UTC
WINDOWS = {'Oct2025': ('2025-10-09', '2025-10-12'), 'Feb2026': ('2026-02-02', '2026-02-08'),
           'Jun2026a': ('2026-06-01', '2026-06-07'), 'Jun2026b': ('2026-06-23', '2026-06-27')}
PAD = 86400
CHUNK = 2000  # mainnet.base.org getLogs limit. base.drpc.org's free plan refused every range we tried, so it is not used.
_blocks = {}


def window_range(name):
    """[start, end) timestamps, start padded by PAD."""
    a, b = WINDOWS[name]
    return day_ts(a) - PAD, day_ts(b) + 86400


def call(method, params, **kw):
    for i in range(6):  # mainnet.base.org 429s in bursts; api.rpc's own backoff is too short for that
        time.sleep(0.25)  # mainnet.base.org 429s under bursts
        try:
            return rpc(method, params, **kw)
        except Exception:
            if i == 5:
                raise
            time.sleep(10 * (i + 1))


def block_ts(n):
    if n not in _blocks:
        _blocks[n] = int(call('eth_getBlockByNumber', [hex(n), False])['timestamp'], 16)
    return _blocks[n]


def block_at(ts):
    """First block with timestamp >= ts (binary search, ~26 calls, cached)."""
    lo, hi = 0, int(call('eth_blockNumber', []), 16)
    while lo < hi:
        mid = (lo + hi) // 2
        if block_ts(mid) < ts:
            lo = mid + 1
        else:
            hi = mid
    return lo


def eth_call(to, data):
    return call('eth_call', [{'to': to, 'data': data}, 'latest'])


def aggregators(proxy):
    """Every phase aggregator of the proxy (the feed was re-pointed between windows)."""
    n = int(eth_call(proxy, '0x58303b10'), 16)  # phaseId()
    out = []
    for i in range(1, n + 1):
        a = eth_call(proxy, '0xc1597304' + hex(i)[2:].zfill(64))  # phaseAggregators(uint16)
        if int(a, 16):
            out.append('0x' + a[-40:])
    assert out[-1] == '0x' + eth_call(proxy, '0x245a7bfc')[-40:]  # aggregator()
    return out


def parse(log):
    price = int(log['topics'][1], 16)
    if price >= 2 ** 255:
        price -= 2 ** 256
    return [int(log['data'], 16), int(log['blockNumber'], 16), price / 1e8]


def fetch_logs(addrs, t0, t1, ck, within_budget):
    """Walks the block range for [t0, t1) in CHUNKs, checkpointing rows and the next block to data/<ck>.json after
    every call. Returns the sorted rows, or None when the budget ran out first."""
    st = load(ck) or dict(b1=block_at(t1) - 1, next=block_at(t0), rows=[])
    b1 = st['b1']
    for a in range(st['next'], b1 + 1, CHUNK):
        if not within_budget():
            return None
        logs = call('eth_getLogs', [{'address': addrs, 'fromBlock': hex(a), 'toBlock': hex(min(a + CHUNK - 1, b1)), 'topics': [ANSWER_UPDATED]}])
        st['rows'] += map(parse, logs)
        st['next'] = a + CHUNK
        save(ck, st)
    return sorted(st['rows'])


def fetch(window, asset, within_budget=lambda: True):
    """Rows for data/oracle/<window>_<asset>.json (fetched if missing), or None when the budget ran out first."""
    name = 'oracle/%s_%s' % (window, asset)
    rows = load(name)
    if rows is not None:
        return rows
    ck = 'cache/oracle_%s_%s' % (window, asset)
    t0, t1 = window_range(window)
    rows = fetch_logs(aggregators(PROXY[asset]), t0, t1, ck, within_budget)
    if rows is None:
        return None
    save(name, rows)
    os.remove(data_path(ck))
    return rows


if __name__ == '__main__':
    within_budget = budget(argv_max_seconds()[0])
    for w in WINDOWS:
        for asset in PROXY:
            rows = fetch(w, asset, within_budget)
            if rows is None:
                print('partial (%s %s), rerun to continue' % (w, asset))
                sys.exit(0)
            ps = [row_price(r) for r in rows]
            print('%-8s %s n=%5d min=%10.2f max=%10.2f' % (w, asset, len(rows), min(ps), max(ps)))
            assert rows == sorted(rows) and len(rows) > 100
    feb = [row_price(r) for r in fetch('Feb2026', 'BTC')]
    assert min(feb) < 61_000 and max(feb) > 75_000, (min(feb), max(feb))
    print('complete')
