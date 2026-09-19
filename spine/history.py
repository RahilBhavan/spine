"""Append one row per market from data/summary.json to data/history.csv (the hourly snapshot series).
Run: .venv/bin/python -m spine.history. Idempotent within the hour: a market whose last row is under 50 minutes old is skipped."""
import csv, os, datetime
from spine.api import DATA, load

OUT = os.path.join(DATA, 'history.csv')
FIELDS = ['utc_ts', 'market', 'borrow_usd', 'collateral_usd', 'book_ltv', 'liq_10', 'liq_20', 'liq_30', 'capacity_ab_usd', 'distance_to_capacity']
MIN_GAP = datetime.timedelta(minutes=50)


def last_ts():
    """{market: datetime of its last row}."""
    if not os.path.exists(OUT):
        return {}
    return {r['market']: datetime.datetime.fromisoformat(r['utc_ts']) for r in csv.DictReader(open(OUT))}


def rows(summary):
    ts = summary['generated_at']
    for name, m in summary['markets'].items():
        st, curve = m['state'], {c['drop']: c['borrow_usd'] for c in m['liquidatable_curve']}
        yield dict(utc_ts=ts, market=name, borrow_usd=round(st['borrow_usd']), collateral_usd=round(st['collateral_usd']),
                   book_ltv=round(st['borrow_usd'] / st['collateral_usd'], 4) if st['collateral_usd'] else '',
                   liq_10=round(curve[0.1]), liq_20=round(curve[0.2]), liq_30=round(curve[0.3]),
                   capacity_ab_usd=round(st['capacity_ab_usd']), distance_to_capacity='' if st['distance_to_capacity'] is None else st['distance_to_capacity'])


def append(summary):
    """Writes the rows that are due; returns how many."""
    last, due = last_ts(), []
    for r in rows(summary):
        if r['market'] not in last or datetime.datetime.fromisoformat(r['utc_ts']) - last[r['market']] >= MIN_GAP:
            due.append(r)
    new = not os.path.exists(OUT)
    with open(OUT, 'a', newline='') as f:
        w = csv.DictWriter(f, FIELDS)
        if new:
            w.writeheader()
        w.writerows(due)
    return len(due)


if __name__ == '__main__':
    summary = load('summary')
    n = append(summary)
    total = sum(1 for _ in csv.DictReader(open(OUT)))
    assert n == 0 or n == len(summary['markets']), n
    assert append(summary) == 0  # same snapshot again: nothing due
    print('history: %d rows appended, %d total, last %s' % (n, total, summary['generated_at']))
