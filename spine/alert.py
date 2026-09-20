"""PLAN §9 item 5: one line per market whose liquidatable borrow exceeds modeled AB capacity within a 10% price move.
Run: .venv/bin/python -m spine.alert [--check] [--summary path]. Prints nothing when no market is that close; the refresh
workflow turns non-empty output into a GitHub issue. stdlib only."""
import json, sys
from spine.api import load

THRESHOLD = 0.10


def alerts(summary, threshold=THRESHOLD):
    out = []
    for name, m in summary['markets'].items():
        d = m['state']['distance_to_capacity']
        if d is None or d > threshold:
            continue
        borrow = next(c['borrow_usd'] for c in m['liquidatable_curve'] if c['drop'] == d)
        out.append('%s: liquidatable borrow exceeds modeled capacity at a -%.0f%% price move (capacity $%.1fM, borrow $%.1fM, snapshot %s)'
                   % (name, 100 * d, m['state']['capacity_ab_usd'] / 1e6, borrow / 1e6, summary['generated_at']))
    return out


def synthetic():
    def market(d):
        return dict(state=dict(distance_to_capacity=d, capacity_ab_usd=1e6),
                    liquidatable_curve=[dict(drop=x / 100, borrow_usd=2e6 if d is not None and x / 100 >= d else 0.0) for x in range(0, 71)])
    return dict(generated_at='2026-01-01T00:00:00+00:00', markets=dict(red=market(0.05), green=market(0.30), none=market(None)))


if __name__ == '__main__':
    args = sys.argv[1:]
    if '--check' in args:
        lines = alerts(synthetic())
        assert len(lines) == 1 and lines[0].startswith('red: ') and '-5% price move' in lines[0] and 'borrow $2.0M' in lines[0], lines
        assert [l.split(':')[0] for l in alerts(synthetic(), threshold=0.30)] == ['red', 'green']
    s = json.load(open(args[args.index('--summary') + 1])) if '--summary' in args else load('summary')
    for line in alerts(s):  # no trailing newline when empty: the workflow tests `[ -s alert.txt ]`
        print(line)
