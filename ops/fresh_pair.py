#!/usr/bin/env python3
"""Bring up ONE fresh pair in ONE ordered operation: claim, seed, start, prove - or touch nothing.

ops/start_pair.py refuses an unseeded dir (the 2026-10-25 runaway), so a fresh run is really claim
stamp -> seed -> start -> prove. This performs it in order and refuses anything it cannot prove.

    python ops/fresh_pair.py --checkout <build> --state <stack>/runNN/state_YYYYMMDD [--dry-run]

--dry-run does every read and validation, prints the plan and the five proofs as PENDING, and writes
nothing: no lock, no stamp, no seed, no process.
--no-spawn does every WRITE up to but not including the engine/UI start (empty-dir gate, key gate,
stamp claim, seed, semantic compare, sleeves, env block) and stops: no engine, no UI, no lock. It is
the only honest way to exercise the start path while another engine is live.

Exit codes: 0 started (or clean dry run), 1 refused or a proof failed, 2 bad arguments.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

OPS = Path(__file__).resolve().parent
sys.path.insert(0, str(OPS))
import start_pair as SP          # engine_path/stack_root/already_running/lock/pointer/DETACHED_ONLY/PY_*
import seed_pair_state as SEED    # select_start/RETENTION_MS/OVERLAP_MS/DEFAULT_INTERVAL_SEC/main
import stop_pair as STOP          # pids()/listener()

LAUNCH_ENV = Path(os.path.expanduser('~/.hermes/state/core_launch_env.json'))
SIGNING_KEY_VAR = 'HL_LIVE_HL_PRIVATE_KEY'   # engine reads this (Core:6809); checked by NAME only
STAMP = 'NETWORK_STAMP'                      # <stack>/NETWORK_STAMP
FIVE = 5
SENTINEL_WALLET = '0x0000000000000000000000000000000000000001'   # run19's shape: one wallet, five sleeves
SLEEVE_INTENT = 'seed_user_owned'
SLEEVE_COINS = ('ORCL', 'AMD', 'NFLX', 'LLY', 'PLATINUM')        # xyz dex, lower-case in position_id
XYZ_DEX = 'xyz'
INFO_URL = 'https://api.hyperliquid-testnet.xyz/info'
ENV_KEYS = ('HL_APP_PORT', 'HL_FOLLOWER_DEXES', 'HL_FOLLOWER_NETWORK', 'HL_LEADER_NETWORK',
            'HL_LIVE_AUDIT_DIR', 'HL_LIVE_CONVERGE_THREAD', 'HL_LIVE_ENV_FILE', 'HL_LIVE_WS_ENABLED',
            'HL_USER_WALLET')


def refuse(msg):
    print('REFUSED: ' + msg, file=sys.stderr)
    return 1


def utc():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def atomic_write(path, text):
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(text, encoding='utf-8')
    os.replace(str(tmp), str(path))


def state_dir_ok(state):
    """(ok, reason): ABSENT or EMPTY, and the <stack>/runNN/state_YYYYMMDD shape the pointer derives from."""
    if not (re.fullmatch(r'state_\d{8}', state.name) and re.fullmatch(r'run\d+', state.parent.name)):
        return False, '--state must look like <stack>/runNN/state_YYYYMMDD, got ' + str(state)
    if state.exists():
        if not state.is_dir():
            return False, str(state) + ' exists and is not a directory'
        left = sorted(p.name for p in state.iterdir())
        if left:
            return False, ('%s is not empty (%d entries, e.g. %s) - a fresh run needs a fresh dir; '
                           'previous dirs are evidence, never reuse or wipe one' % (state, len(left), left[0]))
    return True, ''


def _post(payload, timeout=15.0):
    req = urllib.request.Request(INFO_URL, data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


def live_sleeve_sizes(wallet=SENTINEL_WALLET, coins=SLEEVE_COINS):
    """READ-ONLY exchange truth for the sleeve coins across every dex.

    Returns {COIN: (direction, signed_size, avg_entry_px)}. A coin with no open position is
    FLAT/0.0 - that is measured, not invented. A transport failure raises: it never degrades to FLAT.
    """
    found = {}
    for dex in ('', XYZ_DEX):
        p = {'type': 'clearinghouseState', 'user': wallet}
        if dex:
            p['dex'] = dex
        try:
            d = _post(p)
        except Exception as exc:
            raise RuntimeError('exchange read failed for dex %r: %s: %s'
                               % (dex, type(exc).__name__, exc))
        for ap in (d.get('assetPositions') or []):
            pos = ap.get('position') or {}
            coin = str(pos.get('coin') or '')
            bare = coin.split(':')[-1].upper() if ':' in coin else coin.upper()
            if bare in coins:
                szi = float(pos.get('szi') or 0.0)
                found[bare] = ('LONG' if szi > 0 else 'SHORT' if szi < 0 else 'FLAT', szi,
                               float(pos.get('entryPx') or 0.0))
    return found


def load_sleeves(path):
    """--sleeves JSON: {"sleeves":[{"coin":"ORCL","direction":"LONG","signed_size":0.058,...}]}

    Coin is given BARE (ORCL); the ledger stores the namespaced form (XYZ:ORCL). A coin outside
    SLEEVE_COINS is refused rather than accepted, so a typo cannot become a sleeve the UI cannot match.
    """
    d = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    rows = d.get('sleeves') if isinstance(d, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError('%s needs a non-empty "sleeves" list' % path)
    out = []
    for i, r in enumerate(rows):
        if not isinstance(r, dict):
            raise ValueError('sleeve %d is not an object' % i)
        coin = str(r.get('coin') or '').split(':')[-1].upper()
        if coin not in SLEEVE_COINS:
            raise ValueError('sleeve %d coin %r is not one of %s'
                             % (i, r.get('coin'), list(SLEEVE_COINS)))
        direction = str(r.get('direction') or '').upper()
        if direction not in ('LONG', 'SHORT', 'FLAT'):
            raise ValueError('sleeve %d direction %r is not LONG/SHORT/FLAT' % (i, r.get('direction')))
        size = float(r.get('signed_size') or 0.0)
        if (direction == 'LONG' and size < 0) or (direction == 'SHORT' and size > 0):
            raise ValueError('sleeve %d direction %s disagrees with signed_size %r'
                             % (i, direction, size))
        out.append({'coin': coin, 'direction': direction, 'signed_size': size,
                    'avg_entry_px': float(r.get('avg_entry_px') or 0.0)})
    if len({s['coin'] for s in out}) != len(out):
        raise ValueError('%s names the same coin twice' % path)
    return out


def sleeve_records(sleeves, wallet=SENTINEL_WALLET):
    """run19's exact ManualLedger shape: ONE wallet, namespaced coins, opened_by_intent_id seed_user_owned.

    Copied structurally from run19/state_20261027/manual_live_positions.json (READ-ONLY): position_id is
    <wallet>::<coin-lower>::<DIR>::seed_user_owned, sleeve_id is <wallet>::<COIN-UPPER>, coin is XYZ:<COIN>.
    """
    wl = str(wallet).strip().lower()
    by_coin = {}
    for s in sleeves:
        coin = 'XYZ:' + s['coin']
        by_coin[coin] = {
            'sleeve_id': wl + '::' + coin,
            'position_id': '%s::%s:%s::%s::%s' % (wl, XYZ_DEX, s['coin'], s['direction'], SLEEVE_INTENT),
            'leader_wallet': wl, 'coin': coin, 'direction': s['direction'],
            'signed_size': s['signed_size'], 'avg_entry_px': s['avg_entry_px'],
            'opened_by_intent_id': SLEEVE_INTENT, 'opened_at_ms': 0,
            'last_copy_fill_id': '', 'last_updated_ms': 0}
    net = {c: {'signed_size': v['signed_size']} for c, v in by_coin.items()}
    now = time.time()
    return {'schema': 'manual_live_positions.v1.wallet_sleeves', 'by_wallet': {wl: by_coin},
            'by_coin_net': net, 'updated_at_ms': int(now * 1000),
            'updated_at': time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(now)) + '.000000+00:00'}


def key_gate(environ=None):
    """(ready, env_file, why): a real run's hard gate before ANY process starts.

    The signing key env var being set, or HL_LIVE_ENV_FILE naming a file that EXISTS, is enough.
    Name and presence only - the file is never opened, read, printed or copied (the run18 miss).
    """
    environ = os.environ if environ is None else environ
    env_file = str(environ.get('HL_LIVE_ENV_FILE', '') or '').strip()
    key_present = bool(str(environ.get(SIGNING_KEY_VAR, '') or '').strip())
    env_file_ok = bool(env_file) and Path(env_file).is_file()
    if key_present:
        return True, env_file, '%s is set (name check only)' % SIGNING_KEY_VAR
    if env_file_ok:
        return True, env_file, 'HL_LIVE_ENV_FILE names an existing file (presence check only)'
    if env_file:
        return False, env_file, 'HL_LIVE_ENV_FILE=%r does not exist' % env_file
    return False, '', ('%s is unset and HL_LIVE_ENV_FILE names no file - a real run cannot sign; '
                       'set the var or point HL_LIVE_ENV_FILE at an env file, never paste a key'
                       % SIGNING_KEY_VAR)


def spawn_ui_logged(port, engine_file, env, log):
    """The UI half with stdout/stderr captured into the state dir, stdin closed, console-less.

    DETACHED_PROCESS alone with NO redirect gives invalid handles and uvicorn dies before it binds -
    silently. The log file is what makes that failure visible.
    """
    return subprocess.Popen(
        [SP.PY_PLAIN, '-m', 'uvicorn', 'HL_Copy_App_SSOT:app', '--host', '127.0.0.1',
         '--port', str(port), '--no-access-log'],
        cwd=str(engine_file.parent), env=env, stdin=subprocess.DEVNULL,
        stdout=log, stderr=subprocess.STDOUT, creationflags=SP.DETACHED_ONLY, close_fds=True)


def bring_up(checkout, state, port, env, spawn_engine=None, spawn_ui=None, listener=None,
             sleep=None, wait_s=None):
    """Start the engine, then the UI, and prove BOTH are alive. Returns (engine, ui, error).

    Every edge is injectable so a unit test drives the real control flow with a FAKE spawner:
    no test ever starts a real engine or assumes the caller's process table.
    """
    spawn_engine = SP.spawn_engine if spawn_engine is None else spawn_engine
    spawn_ui = spawn_ui_logged if spawn_ui is None else spawn_ui
    listener = STOP.listener if listener is None else listener
    sleep = time.sleep if sleep is None else sleep
    wait_s = SP.UI_WAIT_S if wait_s is None else wait_s
    engine = spawn_engine(SP.engine_path(checkout), env)
    sleep(SP.SETTLE_S)
    if engine.poll() is not None:
        return engine, None, ('the engine exited %s before the UI started - see %s'
                              % (engine.returncode, state / 'ui_launch.log'))
    state.mkdir(parents=True, exist_ok=True)
    with open(state / 'ui_launch.log', 'ab') as log:
        ui = spawn_ui(port, SP.engine_path(checkout), env, log)
    deadline = time.time() + wait_s
    while time.time() < deadline and listener(port) != ui.pid:
        sleep(1.0)
    if listener(port) != ui.pid:
        return engine, ui, 'the UI did not take :%d - see %s' % (port, state / 'ui_launch.log')
    return engine, ui, None


def launch_env(checkout, state, port, env):
    """The spec core_launch_env.json keeps: cwd/args/env. Env is an allow-list, never a key."""
    engine = SP.engine_path(checkout)
    return {'cwd': str(engine.parent),
            'args': ['--ws', '--loop', '--interval', '10', '--poll-live', '--poll-copy'],
            'env': {k: env[k] for k in ENV_KEYS if k in env},
            'written_at': utc(), 'ui_port': port, 'state': str(state)}


def audit_summary(port, wait=30.0):
    """The UI's own read-only summary, or (None, reason). Measured, not inferred from files."""
    url = 'http://127.0.0.1:%d/api/live-audit-summary' % port
    deadline, last = time.time() + wait, 'no attempt'
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=8) as r:
                return json.loads(r.read().decode('utf-8', 'replace')), ''
        except Exception as exc:
            last = '%s: %s' % (type(exc).__name__, exc)
            time.sleep(1.0)
    return None, last


def proofs(state, port, summary, err, pending):
    """Five proofs, each with its MEASURED value. No measurement is UNKNOWN/PENDING, never PASS."""
    out = []
    rows = (summary or {}).get('live_wallet_rows')
    if isinstance(rows, list) and rows:
        nz = sum(1 for r in rows if abs(float(r.get('signed_size') or 0)) > 1e-9)
        out.append(('a every UI cell zero', 'live_wallet_rows=%d non-zero=%d' % (len(rows), nz), nz == 0))
    else:
        try:
            d = json.loads((state / 'manual_live_positions.json').read_text(encoding='utf-8-sig'))
            sizes = [abs(float(s.get('signed_size') or 0)) for wm in (d.get('by_wallet') or {}).values()
                     if isinstance(wm, dict) for s in wm.values() if isinstance(s, dict)]
            nz = sum(1 for v in sizes if v > 1e-9)
            out.append(('a every UI cell zero', 'ledger sleeves=%d non-zero=%d' % (len(sizes), nz), nz == 0))
        except Exception as exc:
            out.append(('a every UI cell zero', 'UNKNOWN (%s)' % type(exc).__name__, None))

    lg = (summary or {}).get('live_graph') or {}
    if isinstance(lg.get('account_points'), list):
        real = lg.get('realized_pnl_points') if isinstance(lg.get('realized_pnl_points'), list) else []
        out.append(('b graph point ok', 'account_points=%d realized_pnl_points=%d'
                    % (len(lg['account_points']), len(real)), len(lg['account_points']) >= 1))
    else:
        out.append(('b graph point ok', 'UNKNOWN (%s)' % (err or 'no live_graph'), None))

    snap = (summary or {}).get('exchange_account_snapshot') or {}
    if snap:
        out.append(('c account tile', 'status=%s ok=%s account_value=%s'
                    % (snap.get('status'), snap.get('ok'),
                       snap.get('account_value', snap.get('unified_portfolio_value'))), bool(snap.get('ok'))))
    else:
        out.append(('c account tile', 'UNKNOWN (%s)' % (err or 'no exchange_account_snapshot'), None))

    try:
        d = json.loads((state / 'manual_live_positions.json').read_text(encoding='utf-8-sig'))
        owned = []
        for w, wm in (d.get('by_wallet') or {}).items():
            if not isinstance(wm, dict):
                continue
            for coin, s in wm.items():
                if not isinstance(s, dict):
                    continue
                if (str(s.get('opened_by_intent_id') or '') == SLEEVE_INTENT
                        and str(s.get('leader_wallet', '')).lower() == str(w).lower()
                        and str(s.get('sleeve_id', '')).startswith(str(w) + '::')
                        and str(s.get('coin') or '').upper() == str(coin).upper()):
                    owned.append('%s:%s' % (str(w)[:10], coin))
        out.append(('d five sleeves USER-OWNED', 'schema=%s owned=%d [%s]'
                    % (d.get('schema'), len(owned), ','.join(sorted(owned))[:90] or '-'),
                    d.get('schema') == 'manual_live_positions.v1.wallet_sleeves'
                    and len(owned) >= FIVE))
    except Exception as exc:
        out.append(('d five sleeves USER-OWNED', 'UNKNOWN (%s)' % type(exc).__name__, None))

    try:
        e = STOP.pids(state)
        out.append(('e exactly one engine', 'pids=' + str(e or []), len(e) == 1))
    except Exception as exc:
        out.append(('e exactly one engine', 'UNKNOWN (%s)' % type(exc).__name__, None))

    for name, measured, ok in out:
        if pending:
            verdict = 'PENDING'
        else:
            verdict = 'PASS' if ok else ('FAIL' if ok is False else 'UNKNOWN')
        print('  %-26s %-56s %s' % (name, measured, verdict))
    return (not pending) and all(ok for _, _, ok in out)


def main(argv=None):
    ap = argparse.ArgumentParser(description='fresh pair: claim, seed, start, prove - or touch nothing')
    ap.add_argument('--checkout', required=True)
    ap.add_argument('--state', required=True)
    ap.add_argument('--seed', default='C:/tmp/run15_stage/live_config_seed.json')
    ap.add_argument('--sleeves', default='',
                    help='JSON with a "sleeves" list; default: read live exchange truth for the sleeve coins')
    ap.add_argument('--ui-port', type=int, default=SP.UI_PORT)
    ap.add_argument('--send-mode', choices=('off', 'close', 'on'), default='off')
    ap.add_argument('--leader-network', default=os.environ.get('HL_LEADER_NETWORK', 'testnet'))
    ap.add_argument('--follower-network', default=os.environ.get('HL_FOLLOWER_NETWORK', 'testnet'))
    ap.add_argument('--user-wallet', default=os.environ.get('HL_USER_WALLET', ''))
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--no-spawn', action='store_true',
                    help='do every write up to but not including the engine/UI start, then stop')
    a = ap.parse_args(argv)

    checkout = Path(a.checkout).expanduser()
    state = Path(a.state).expanduser()
    stack = SP.stack_root(state)
    pointer = stack / 'CURRENT_AUDIT_DIR'

    # read-only validation, shared by dry run and real run
    if not SP.engine_path(checkout).exists():
        return refuse('no engine at %s - not a pair checkout' % SP.engine_path(checkout))
    seed_path = Path(a.seed).expanduser()
    if not seed_path.exists():
        return refuse('seed %s does not exist' % seed_path)
    ok, why = state_dir_ok(state)
    if not ok:
        return refuse(why)
    seed = json.loads(seed_path.read_text(encoding='utf-8-sig'))
    wallets = list(seed.get('wallets') or {})
    if len(wallets) < FIVE:
        return refuse('the seed names %d wallets; five sleeves need at least %d' % (len(wallets), FIVE))
    stamp = stack / STAMP
    prior_stamp = stamp.read_text(encoding='utf-8').strip() if stamp.exists() else 'ABSENT'

    # sleeves: explicit --sleeves JSON, else live exchange truth for the five coins (READ-ONLY)
    if a.sleeves:
        try:
            sleeves = load_sleeves(a.sleeves)
            sleeves_src = 'file:' + str(a.sleeves)
        except Exception as exc:
            return refuse('--sleeves is unusable: %s: %s' % (type(exc).__name__, exc))
    else:
        try:
            live = live_sleeve_sizes()
        except Exception as exc:
            return refuse('live exchange truth is unavailable: %s: %s' % (type(exc).__name__, exc))
        sleeves = [{'coin': c, 'direction': live.get(c, ('FLAT', 0.0, 0.0))[0],
                    'signed_size': live.get(c, ('FLAT', 0.0, 0.0))[1],
                    'avg_entry_px': live.get(c, ('FLAT', 0.0, 0.0))[2]} for c in SLEEVE_COINS]
        sleeves_src = 'live exchange truth (read-only)'
    if len(sleeves) != FIVE:
        return refuse('the sleeve set has %d entries; exactly %d are required (one per coin)'
                      % (len(sleeves), FIVE))
    if sleeves_src.startswith('live') and all(s['direction'] == 'FLAT' for s in sleeves):
        print('sleeves flat: no user positions to label (the five rows are still written)')

    # signing key: a real run HARD REFUSES before any process unless the env var is set or HL_LIVE_ENV_FILE
    # names an existing file. Name and presence only - the file is never read here (the run18 miss).
    if a.dry_run:
        blocked = SP.already_running(state, a.ui_port) if state.exists() else None
        if blocked:
            return refuse(blocked)
        pstate, _prev = SP.read_pointer(pointer)
        now_ms = int(time.time() * 1000)
        interval_ms = SEED.DEFAULT_INTERVAL_SEC * 1000
        cursor = now_ms + interval_ms + SEED.OVERLAP_MS
        print(json.dumps({'dry_run': True, 'touches': 'nothing', 'plan': {
            'checkout': str(checkout), 'state': str(state), 'state_absent': not state.exists(),
            'seed': str(seed_path), 'seed_wallets': len(wallets),
            'sleeves_source': sleeves_src,
            'sleeves': [{'coin': s['coin'], 'direction': s['direction'],
                         'signed_size': s['signed_size']} for s in sleeves],
            'sleeve_wallet': SENTINEL_WALLET, 'sleeve_intent': SLEEVE_INTENT,
            'network_stamp': {'path': str(stamp), 'prior_state': prior_stamp,
                              'would_claim': a.follower_network},
            'seed_math': {'t0_ms': now_ms, 'cursor_ms': cursor,
                          'select_start_equals_t0': SEED.select_start(
                              cursor, now_ms, interval_ms, SEED.OVERLAP_MS) == now_ms,
                          'retention_ms': SEED.RETENTION_MS, 'overlap_ms': SEED.OVERLAP_MS},
            'signing_key_env': SIGNING_KEY_VAR,
            'signing_key': 'PRESENT' if os.environ.get(SIGNING_KEY_VAR) else 'ABSENT',
            'signing_key_note': 'checked by NAME only; the value is never read, printed or copied',
            'engine': str(SP.engine_path(checkout)), 'ui_port': a.ui_port,
            'ui_launch_log': str(state / 'ui_launch.log'), 'launch_env': str(LAUNCH_ENV),
            'pointer': {'path': str(pointer), 'state': pstate}, 'send_mode': a.send_mode}},
            indent=2))
        print('five proofs (PENDING - nothing has started):')
        proofs(state, a.ui_port, None, '', pending=True)
        print('DRY RUN - nothing written, no process started, no lock taken.')
        return 0

    # GATE: a real run (spawning or --no-spawn) refuses here, before anything is written or started.
    key_ready, env_file, why = key_gate()
    print('key gate        %s: %s' % ('PASS' if key_ready else 'REFUSE', why))
    if not key_ready:
        return refuse(why)

    # 1+2. claim the network stamp ALONE, from ABSENT or the same claim
    if not state.exists():
        state.mkdir(parents=True)
    if prior_stamp not in ('ABSENT', a.follower_network):
        return refuse('%s already claims %r and this run is %r - release it deliberately, never overwrite'
                      % (stamp, prior_stamp, a.follower_network))
    atomic_write(stamp, a.follower_network + '\n')
    print('network stamp  %s: prior=%s now=%s' % (stamp, prior_stamp, a.follower_network))

    # 3. seed through the seeder (it owns the cursor/anchor/change-log maths)
    seed_argv = [sys.executable, str(OPS / 'seed_pair_state.py'),
                 '--state-dir', str(state), '--seed', str(seed_path),
                 '--start-ms', str(int(time.time() * 1000)), '--send-mode', a.send_mode]
    seed_proc = subprocess.run(seed_argv, cwd=str(OPS.parent), capture_output=True, text=True)
    sys.stdout.write(seed_proc.stdout)
    if seed_proc.stderr:
        sys.stderr.write(seed_proc.stderr)
    rc = seed_proc.returncode
    if rc != 0:
        return refuse('the seeder exited %d - the dir is not usable; do not start' % rc)
    written = json.loads((state / 'live_config.json').read_text(encoding='utf-8-sig'))
    expect = dict(seed)
    expect['global_controls'] = dict(seed.get('global_controls') or {}, send_mode=a.send_mode.upper())
    if written == expect:
        print('config vs seed  MATCH (semantic: parsed JSON equality)')
    else:
        diff = sorted(k for k in set(list(written) + list(expect)) if written.get(k) != expect.get(k))
        print('config vs seed  DIFFERS in top-level keys: ' + str(diff))
        return refuse('the written config is not the seed (%s)' % diff)

    # 4. five user sleeves in ManualLedger's on-disk shape (run19's shape: one wallet, five coins)
    ledger = state / 'manual_live_positions.json'
    atomic_write(ledger, json.dumps(sleeve_records(sleeves), indent=2, sort_keys=True))
    print('sleeves         wrote %s from %s (%d coins on %s, intent %s): %s'
          % (ledger.name, sleeves_src, len(sleeves), SENTINEL_WALLET, SLEEVE_INTENT,
             ','.join('%s %s %s' % (s['coin'], s['direction'], s['signed_size']) for s in sleeves)))

    # 5. signing key: name only
    print('signing key     %s: %s' % (SIGNING_KEY_VAR, 'PRESENT' if os.environ.get(SIGNING_KEY_VAR)
                                      else 'ABSENT (engine runs with no exchange client)'))

    # 6. one env for both halves
    env = dict(os.environ)
    for k in list(env):
        if k.startswith('PYTHON'):
            env.pop(k)      # a stray PYTHONPATH/PYTHONHOME makes the 3.14 UI exit instantly and silently
    env.update({'HL_LIVE_AUDIT_DIR': str(state), 'HL_APP_PORT': str(a.ui_port),
                'HL_LEADER_NETWORK': a.leader_network, 'HL_FOLLOWER_NETWORK': a.follower_network,
                'HL_LIVE_WS_ENABLED': env.get('HL_LIVE_WS_ENABLED', '1'),
                'HL_LIVE_CONVERGE_THREAD': env.get('HL_LIVE_CONVERGE_THREAD', '1')})
    if a.user_wallet:
        env['HL_USER_WALLET'] = a.user_wallet

    if a.no_spawn:
        # every write is done, the engine/UI start is NOT. Key NAMES only - never a value.
        print('env block       %d keys (names only): %s'
              % (len(env), ','.join(sorted(k for k in env if k.startswith('HL_')))))
        print('launch env keys (allow-list): %s' % ','.join(k for k in ENV_KEYS if k in env))
        print('NO-SPAWN - stopped before the engine and the UI. No lock taken, nothing started.')
        return 0

    lock = stack / '.fresh_pair.lock'
    got, lock_fd = SP.acquire_lock(lock)
    if got != 'ok':
        return refuse('another start is in progress on %s (lock pid %s)' % (stack, lock_fd or '?'))
    engine = ui = None
    try:
        blocked = SP.already_running(state, a.ui_port)
        if blocked:
            return refuse(blocked)
        engine, ui, err = bring_up(checkout, state, a.ui_port, env)
        if err:
            return refuse(err)

        # 7. launch env (allow-listed env only, never a key) and the pointer
        LAUNCH_ENV.parent.mkdir(parents=True, exist_ok=True)
        spec = launch_env(checkout, state, a.ui_port, env)
        atomic_write(LAUNCH_ENV, json.dumps(spec, indent=2))
        atomic_write(pointer, str(state) + '\n')
        print('launch env      %s (cwd/args/env, %d env keys, no key material)'
              % (LAUNCH_ENV, len(spec['env'])))
        print('pointer         %s -> %s' % (pointer, state))

        # 8+9. measure
        summary, err = audit_summary(a.ui_port)
        print('engine pid %d  ui pid %d  started %s' % (engine.pid, ui.pid, utc()))
        ok = proofs(state, a.ui_port, summary, err, pending=False)
        print('VERDICT=' + ('PASS' if ok else 'FAIL'))
        return 0 if ok else 1
    finally:
        SP.release_lock(lock, lock_fd)


if __name__ == '__main__':
    sys.exit(main())
