"""spine.alert on three synthetic markets: one within 10% of capacity, one well past it, one that never crosses.
Run: .venv/bin/python -m pytest -q tests"""
from spine.alert import alerts, synthetic


def test_alerts():
    lines = alerts(synthetic())
    assert len(lines) == 1
    assert lines[0].startswith('red: ') and 'green' not in lines[0] and 'none' not in lines[0]
    assert '-5% price move' in lines[0] and 'capacity $1.0M' in lines[0] and 'borrow $2.0M' in lines[0] and '2026-01-01T00:00:00+00:00' in lines[0]
    assert [l.split(':')[0] for l in alerts(synthetic(), threshold=0.30)] == ['red', 'green']
    assert alerts(synthetic(), threshold=0.01) == []


def test_alert_at_threshold():
    s = synthetic()
    s['markets']['green']['state']['distance_to_capacity'] = 0.10  # exactly at the threshold: site/app.js shows red there too
    assert [l.split(':')[0] for l in alerts(s)] == ['red', 'green']
