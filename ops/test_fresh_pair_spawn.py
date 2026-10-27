"""Unit tests for ops/fresh_pair.py that NEVER start a real engine or UI.

Every process edge is injected: the spawner returns a fake handle, the listener is a dict, sleep is a
no-op. That is the only honest way to cover the start path while another engine is live.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fresh_pair as FP


class FakeProc(object):
    def __init__(self, pid, rc=None):
        self.pid = pid
        self.returncode = rc

    def poll(self):
        return self.returncode


def env_with(**kw):
    d = {'PATH': 'x'}
    d.update(kw)
    return d


def test_key_gate_refuses_without_key_and_without_env_file():
    ok, _env_file, why = FP.key_gate(env_with())
    assert ok is False, why
    assert 'unset' in why and 'HL_LIVE_ENV_FILE names no file' in why


def test_key_gate_passes_when_key_var_is_set():
    ok, _env_file, why = FP.key_gate(env_with(**{FP.SIGNING_KEY_VAR: 'dummy'}))
    assert ok is True, why
    assert 'set' in why


def test_key_gate_passes_on_env_file_presence_only():
    p = HERE / '_probe_env_presence.env'
    p.write_text('', encoding='utf-8')
    try:
        ok, env_file, why = FP.key_gate(env_with(HL_LIVE_ENV_FILE=str(p)))
        assert ok is True, why
        assert env_file == str(p)
        assert 'presence check only' in why
    finally:
        p.unlink()


def test_key_gate_refuses_a_named_file_that_does_not_exist():
    missing = str(HERE / '_no_such_file.env')
    ok, _env_file, why = FP.key_gate(env_with(HL_LIVE_ENV_FILE=missing))
    assert ok is False, why
    assert 'does not exist' in why


def test_sleeve_records_match_run19_shape():
    sleeves = FP.load_sleeves(HERE / 'sample_sleeves_run19.json')
    assert len(sleeves) == 5
    rec = FP.sleeve_records(sleeves)
    assert rec['schema'] == 'manual_live_positions.v1.wallet_sleeves'
    by = rec['by_wallet'][FP.SENTINEL_WALLET]
    assert sorted(by) == ['XYZ:AMD', 'XYZ:LLY', 'XYZ:NFLX', 'XYZ:ORCL', 'XYZ:PLATINUM']
    orcl = by['XYZ:ORCL']
    assert orcl['position_id'] == FP.SENTINEL_WALLET + '::xyz:ORCL::LONG::seed_user_owned', orcl
    assert orcl['sleeve_id'] == FP.SENTINEL_WALLET + '::XYZ:ORCL'
    assert orcl['opened_by_intent_id'] == 'seed_user_owned'
    assert rec['by_coin_net']['XYZ:AMD']['signed_size'] == -0.046


def test_load_sleeves_refuses_an_unknown_coin():
    p = HERE / '_probe_bad_sleeves.json'
    p.write_text(json.dumps({'sleeves': [{'coin': 'BTC', 'direction': 'LONG', 'signed_size': 1}]}),
                 encoding='utf-8')
    try:
        FP.load_sleeves(p)
        raise AssertionError('an unknown coin was accepted')
    except ValueError as exc:
        assert 'not one of' in str(exc)
    finally:
        p.unlink()


def test_bring_up_starts_engine_then_ui_and_proves_the_listener():
    calls = []
    log_dir = HERE / '_probe_bring_up'
    log_dir.mkdir(exist_ok=True)

    def spawn_engine(engine_file, env):
        calls.append(('engine', engine_file.name, env.get('HL_APP_PORT')))
        return FakeProc(111)

    def spawn_ui(port, engine_file, env, log):
        calls.append(('ui', port, engine_file.name))
        return FakeProc(222)

    engine, ui, err = FP.bring_up(HERE, log_dir, 5555, {'HL_APP_PORT': '5555'},
                                  spawn_engine=spawn_engine, spawn_ui=spawn_ui,
                                  listener=lambda p: {5555: 222}.get(p),
                                  sleep=lambda s: None, wait_s=3)
    assert err is None, err
    assert engine.pid == 111 and ui.pid == 222
    assert [c[0] for c in calls] == ['engine', 'ui'], calls


def test_bring_up_refuses_when_the_engine_dies_before_the_ui():
    log_dir = HERE / '_probe_bring_up_dead'
    log_dir.mkdir(exist_ok=True)
    spawned = []

    def spawn_engine(engine_file, env):
        spawned.append('engine')
        return FakeProc(333, rc=7)

    def spawn_ui(port, engine_file, env, log):
        spawned.append('ui')
        return FakeProc(444)

    _engine, _ui, err = FP.bring_up(HERE, log_dir, 5556, {}, spawn_engine=spawn_engine,
                                    spawn_ui=spawn_ui, listener=lambda p: None,
                                    sleep=lambda s: None, wait_s=3)
    assert err and 'exited 7 before the UI started' in err, err
    assert spawned == ['engine'], spawned


def test_bring_up_refuses_when_the_ui_never_takes_the_port():
    log_dir = HERE / '_probe_bring_up_noport'
    log_dir.mkdir(exist_ok=True)
    _engine, _ui, err = FP.bring_up(
        HERE, log_dir, 5557, {},
        spawn_engine=lambda f, e: FakeProc(555),
        spawn_ui=lambda p, f, e, l: FakeProc(666),
        listener=lambda p: None, sleep=lambda s: None, wait_s=0)
    assert err and 'did not take :5557' in err, err
