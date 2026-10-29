"""spine.whatif on the committed data in data/ (no network, no positions_*.json)."""
import math
import socket
import pytest
from spine import api, backtest, whatif
from spine.backtest import CALIB, DEFAULTS, key, saved_runs

BOOK = '2026-06-01'
ARGS = ['--market', 'cbBTC', '--book', BOOK]
# stored runs used the depth snapshot of the hour they ran in (not kept); at today's data/depth.json this one lands 5% lower on liquidated_usd
DEPTH_DRIFT = {('event:Feb2026', 'cbBTC')}


def test_default_event_replay_reproduces_the_stored_calibration_row():
    stored = {(r['market'], r['book'], r['calib_window']): r for r in saved_runs() if 'calib_window' in r
              and r['scenario'] == 'AB' and r['resp_share'] == 0.7 and r['react_min'] == 120 and r['full_below_usd'] == 0 and r['cex_cap_usd'] == DEFAULTS['cex_cap_usd']}
    loaded = whatif.load_book('cbBTC', BOOK)
    res, _ = whatif.replay('cbBTC', BOOK, 'event:Jun2026a', loaded=loaded)
    row = stored['cbBTC', BOOK, 'Jun2026a']
    assert (res['lltv'], res['cap'], res['scenario'], res['resp_share'], res['react_min']) == (0.86, 0.75, 'AB', 0.7, 120)
    for k in whatif.COMPARED:
        assert math.isclose(res[k], row[k], rel_tol=1e-9, abs_tol=1e-6), k
    assert whatif.compare_stored(res)[0] == 'reproduced'


@pytest.mark.parametrize('cw,date,market', [(cw, date, m) for cw, _, date, mk in CALIB for m in mk])
def test_every_stored_calibration_event_reproduces_or_is_flagged(cw, date, market):
    res, _ = whatif.replay(market, date, 'event:' + cw)
    status, detail = whatif.compare_stored(res)
    assert status == ('differs' if ('event:' + cw, market) in DEPTH_DRIFT else 'reproduced'), detail


def test_crash_path_replay_is_run_with_the_requested_parameters():
    res, notes = whatif.replay('cbBTC', BOOK, 'Mar2020', lltv=0.80, multiple=3)
    raw, book = whatif.load_book('cbBTC', BOOK)
    star = backtest.calibrated()
    direct = backtest.run('cbBTC', 'Mar2020', book, api.load('depth'), backtest.candles_for('cbBTC', 'Mar2020'), lltv=0.80, cap=0.75, scenario='AB',
                          resp_share=star[0], react_min=star[1], full_below_usd=star[2], cex_cap_usd=3 * DEFAULTS['cex_cap_usd'])
    assert (res['trough_exposure_usd'], res['realized_bad_debt_usd']) == (direct['trough_exposure_usd'], direct['realized_bad_debt_usd'])
    assert res['trough_exposure_usd'] > 0 and notes == []
    assert whatif.compare_stored(res)[0] == 'none'  # no stored run for a hypothetical path on a committed book
    more, _ = whatif.replay('cbBTC', BOOK, 'Mar2020', lltv=0.80, multiple=10)
    assert more['trough_exposure_usd'] < res['trough_exposure_usd']


def test_cli_names_book_path_parameters_and_prints_the_two_measures_apart(capsys):
    whatif.main(ARGS + ['--path', 'Mar2020', '--lltv', '0.80', '--capital-multiple', '3'])
    out = capsys.readouterr().out
    assert 'cbBTC 2026-06-01' in out and 'data/book_cbBTC_2026-06-01.json' in out and 'path:       Mar2020' in out
    assert 'LLTV 0.8,' in out and 'cap 0.75' in out and '$303.3M' in out and '3x the observed' in out and 'resp_share 0.7' in out and 'react_min 120' in out
    lines = out.splitlines()
    unserved = [l for l in lines if l.startswith('underwater_unserved_at_trough:')]
    realized = [l for l in lines if l.startswith('realized_loss:')]
    assert len(unserved) == len(realized) == 1 and unserved[0] != realized[0]
    assert 'not added' in out and 'total' not in unserved[0] + realized[0]


def test_cli_event_path_says_cap_does_not_apply_and_reports_the_stored_match(capsys):
    whatif.main(ARGS + ['--path', 'event:Jun2026a'])
    out = capsys.readouterr().out
    assert 'cap does not apply' in out and 'stored-run check: reproduced' in out


def test_unknown_names_list_the_valid_choices(capsys):
    with pytest.raises(SystemExit) as e:
        whatif.main(['--market', 'nope', '--book', BOOK, '--path', 'Mar2020'])
    assert 'unknown market' in str(e.value) and 'cbBTC' in str(e.value) and 'WETH' in str(e.value)
    with pytest.raises(SystemExit) as e:
        whatif.main(['--market', 'SOL', '--book', BOOK, '--path', 'Mar2020'])
    assert 'known market but has no committed book' in str(e.value)
    with pytest.raises(SystemExit) as e:
        whatif.main(['--market', 'cbBTC', '--book', '1999-01-01', '--path', 'Mar2020'])
    assert 'no committed book' in str(e.value) and BOOK in str(e.value) and '2025-10-09' in str(e.value)
    with pytest.raises(SystemExit) as e:
        whatif.main(ARGS + ['--path', 'Mar1999'])
    msg = str(e.value)
    assert 'unknown path' in msg and 'Mar2020' in msg and 'Jun2026' in msg and 'event:Jun2026a' in msg
    with pytest.raises(SystemExit) as e:
        whatif.main(ARGS + ['--path', 'event:Feb2026'])  # a real event, but of another book
    assert 'unknown path' in str(e.value)
    whatif.main(['--list'])
    assert 'cbBTC 2026-06-01' in capsys.readouterr().out


@pytest.mark.parametrize('bad', [['--lltv', '1.5'], ['--lltv', 'x'], ['--capital-multiple', '0'], ['--scenario', 'Z'], ['--nope', '1'], ['--lltv']])
def test_bad_flags_exit_with_a_message(bad):
    with pytest.raises(SystemExit) as e:
        whatif.main(ARGS + ['--path', 'Mar2020'] + bad)
    assert str(e.value).startswith('error: ')


def test_runs_offline_from_committed_files_only(monkeypatch):
    seen = []
    real = api.load
    def spy(name):
        seen.append(name)
        return real(name)
    for mod in (api, backtest, whatif):
        monkeypatch.setattr(mod, 'load', spy)
    def no_net(*a, **k):
        raise AssertionError('network used')
    monkeypatch.setattr(socket.socket, 'connect', no_net)
    whatif.replay('cbBTC', BOOK, 'Mar2020')
    assert 'book_cbBTC_%s' % BOOK in seen and not any(n.startswith('positions_') for n in seen)


def test_bench_times_the_stress_grid_cells():
    b = whatif.bench('cbBTC', BOOK, paths=['Mar2020'])
    assert b['cells'] == len(whatif.LLTV_CAP) * len(whatif.CAPITAL_MULTIPLES) == 20 and b['positions'] == 30216
    assert 0 < b['min_s'] <= b['median_s'] <= b['max_s'] and b['total_s'] > 0
    assert 'stress-grid cells' in whatif.bench_report(b)
