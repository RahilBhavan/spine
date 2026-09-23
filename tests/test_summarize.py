"""Invariants of spine.summarize's per-market aggregates on five synthetic positions (ROADMAP Phase G3).
Run: .venv/bin/python -m pytest -q tests"""
import pytest
from spine.api import lif
from spine.summarize import DROPS, HF_STEPS, distance_to_capacity, hf_cdf, liquidatable_curve, ltv_hist, report

LLTV = 0.86
# same keys summarize_market builds: two Coinbase, one over LLTV, one with zero collateral (ltv 1.0, as summarize_market sets it), one healthy
POS = [dict(ltv=0.50, borrow_usd=100.0, collateral_usd=200.0, health_factor=LLTV / 0.50, is_coinbase=True),
       dict(ltv=0.80, borrow_usd=400.0, collateral_usd=500.0, health_factor=LLTV / 0.80, is_coinbase=True),
       dict(ltv=0.90, borrow_usd=90.0, collateral_usd=100.0, health_factor=LLTV / 0.90, is_coinbase=False),
       dict(ltv=1.0, borrow_usd=10.0, collateral_usd=0.0, health_factor=None, is_coinbase=False),
       dict(ltv=0.30, borrow_usd=300.0, collateral_usd=1000.0, health_factor=LLTV / 0.30, is_coinbase=False)]
TOTAL = sum(p['borrow_usd'] for p in POS)


def curve():
    return liquidatable_curve(POS, LLTV, 1 / lif(LLTV))


def test_ltv_hist():
    bins = ltv_hist(POS)
    assert len(bins) == 50
    assert sum(b['borrow_usd'] for b in bins) == TOTAL
    assert sum(b['cb_borrow_usd'] for b in bins) == sum(p['borrow_usd'] for p in POS if p['is_coinbase']) == 500.0
    assert bins[-1]['borrow_usd'] == 10.0  # ltv 1.0 lands in the top bin, not past it


def test_liquidatable_curve():
    c = curve()
    assert [r['drop'] for r in c] == DROPS
    b = [r['borrow_usd'] for r in c]
    assert all(x <= y for x, y in zip(b, b[1:]))
    assert c[0]['borrow_usd'] == sum(p['borrow_usd'] for p in POS if p['ltv'] > LLTV) == 100.0
    at70 = next(r for r in c if r['drop'] == 0.70)
    assert at70['borrow_usd'] == TOTAL and at70['count'] == len(POS)
    assert all(r['bad_borrow_usd'] <= r['borrow_usd'] for r in c)


def test_distance_to_capacity():
    c = curve()
    assert distance_to_capacity(c, 50.0) == 0.0
    assert distance_to_capacity(c, 100.0) == 0.07  # the 0.80 position crosses at 0.80 / 0.93 > lltv
    assert distance_to_capacity(c, 0) is None and distance_to_capacity(c, None) is None
    assert distance_to_capacity(c, TOTAL) is None and distance_to_capacity(c, 1e9) is None


def test_hf_cdf():
    hp = [dict(p, health_factor=h) for p, h in zip(POS, (1.2, 1.5, 2.0, 2.9, 1.01))]  # all within [1, 3)
    cdf = hf_cdf(hp)
    assert len(cdf) == len(HF_STEPS) == 40
    s = [r['share'] for r in cdf]
    assert s[0] == 0 and s[-1] == 1.0 and all(x <= y for x, y in zip(s, s[1:]))
    hp[0]['health_factor'] = None
    assert hf_cdf(hp)[-1]['share'] == (TOTAL - hp[0]['borrow_usd']) / TOTAL


def test_report_warns_without_check():
    c = curve()  # POS has the 0.90 position at HF < 1, as in a crash; depth is empty, as when depth.json is missing
    state = dict(borrow_usd=TOTAL, price=1.0, n_positions=len(POS), coinbase_share_borrow=0.5, lltv=LLTV,
                 capacity_ab_usd=0.0, distance_to_capacity=distance_to_capacity(c, 0.0))
    out = dict(markets=dict(cbBTC=dict(state=state, ltv_hist=ltv_hist(POS), liquidatable_curve=c, hf_cdf=hf_cdf(POS), depth={})),
               totals=dict(borrow_usd=TOTAL, n_positions=len(POS), coinbase_share_borrow=0.5))
    report(out)
    with pytest.raises(AssertionError):
        report(out, check=True)
