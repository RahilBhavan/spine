"""spine.fetch_positions.walk against a fake API: a book over several pages, dust first, shares past 2**53.
Run: .venv/bin/python -m pytest -q tests"""
import pytest
import spine.fetch_positions as fp


def book(n):
    big = 2 ** 60
    return [dict(user={'address': '0x%040x' % i}, healthFactor=None if i < 30 else 1.0 + i,
                 state={'borrowShares': i + 1 if i < 30 else str(big + i // 2)}) for i in range(n)]


def fake_page(rows, calls):
    def page(where):
        calls.append(where['borrowShares_gte'])
        assert isinstance(where['borrowShares_gte'], str)
        lo = int(where['borrowShares_gte'])
        hits = sorted((r for r in rows if int(r['state']['borrowShares']) >= lo), key=lambda r: int(r['state']['borrowShares']))
        for r in rows:  # the oracle moves between requests; the walk must not depend on it
            if r['healthFactor'] is not None:
                r['healthFactor'] *= 0.97
        return len(hits), hits[:1000]
    return page


def test_walk_returns_every_position(monkeypatch):
    rows, calls = book(2500), []
    monkeypatch.setattr(fp, 'page', fake_page(rows, calls))
    seen = fp.walk({})
    assert set(seen) == {r['user']['address'] for r in rows}
    assert len(calls) == 3


def test_fetch_raises_on_a_truncated_walk(monkeypatch):
    rows = book(2500)
    page = fake_page(rows, [])
    monkeypatch.setattr(fp, 'page', lambda where: (len(rows) + fp.CHURN + 1, page(where)[1]))
    with pytest.raises(RuntimeError, match='walked 2500 positions'):
        fp.fetch('0xmarket')
