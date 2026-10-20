'''ENG-INV-11: Core truth reads must follow the MASTER address (HL_LIVE_HL_ACCOUNT_ADDRESS), never the
signer, never HL_USER_WALLET; an invalid identity fails closed through the existing unreadable holds.

Offline only: every /info call is answered by an in-process double. Run: python test_inv11_identity_routing.py
'''
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
MASTER = '0x' + 'a' * 40
SIGNER = '0x' + 'b' * 40
LEGACY = '0x' + 'c' * 40  # HL_USER_WALLET: must never be read as truth
_p = _f = 0


def check(name, ok, detail=''):
    global _p, _f
    if ok:
        _p += 1
        print('  PASS: ' + name)
    else:
        _f += 1
        print('  FAIL: ' + name + '  ::  ' + str(detail)[:600])


PROBE = r'''
import json, os, sys
sys.path.insert(0, os.environ['ENGINE_DIR'])
import HL_Live_Copy_Service_Core as c

calls = []


def fx(payload):
    calls.append(dict(payload))
    t = payload.get('type')
    if t == 'perpDexs':
        return [{'name': 'xyz'}]
    if t == 'clearinghouseState':
        return {'marginSummary': {'accountValue': '1000'},
                'assetPositions': [{'position': {'coin': 'BTC', 'szi': '2', 'positionValue': '200'}}]}
    if t == 'portfolio':
        return [['day', {'pnlHistory': [[0, '0'], [1, '-5']], 'accountValueHistory': [[1, '1000']]}]]
    if t == 'userFillsByTime':
        return [{'oid': 1, 'coin': 'BTC', 'side': 'B', 'sz': '1', 'px': '100', 'time': 5}]
    return {}


class Resp:
    def __init__(self, body):
        self._body = body

    def json(self):
        return self._body


class Req:
    @staticmethod
    def post(url, json=None, timeout=None):
        return Resp(fx(json or {}))


c.EXPOSURE_FETCHER = fx
c.MIDS_FETCHER = fx
c.requests = Req
c._FOLLOWER_MIDS['dexes'] = ['']
c.USER_WALLET = os.environ.get('HL_USER_WALLET', '')
out = {}

out['truth'] = c._truth_master_address()
out['mark'] = c.follower_position_mark('BTC')
ib = c.IntentBuilder(c.ConfigManager(), c.ManualLedger())
ib._exposure = None
out['exposure'] = ib.follower_exposure()
out['snapshot'] = c.ExchangeReconciler(c.ManualLedger(), c.AuditLogWriter()).fetch_snapshot()[1]
# fixture PnL is -5 over the day, so a 4 USD limit must engage: proves the read is live, not unreadable
c.atomic_write_json(c.LIVE_CONFIG_FILE, {'wallets': {}, 'global_controls': {'max_daily_loss_usd': 4}})
core = c.LiveCopyCore()
out['limit'] = core.cfg.max_daily_loss()
out['cfg_exists'] = c.LIVE_CONFIG_FILE.exists()
out['daily_block'] = core._daily_loss_block()
core.copy_ingestor = c.CopyAccountIngestor()
core.run_cycle(use_source_csv=False, poll_live=False, poll_copy=True)
out['copy_seen'] = [dict(p) for p in calls if p.get('type') == 'userFillsByTime']
out['users'] = sorted({str(p.get('user')) for p in calls if p.get('user')})
out['calls'] = calls
print('PROBE_JSON ' + json.dumps(out))
'''


def run_probe(env_extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith('HL_')}
    tmp = tempfile.mkdtemp(prefix='inv11_')
    env.update({'ENGINE_DIR': str(HERE), 'HL_LIVE_AUDIT_DIR': tmp, 'HL_LIVE_ENV_FILE': str(Path(tmp) / 'none.env'),
                'HL_LEADER_NETWORK': 'mainnet', 'HL_FOLLOWER_NETWORK': 'testnet'})
    env.update(env_extra)
    script = Path(tmp) / 'probe.py'
    script.write_text(PROBE, encoding='utf-8')
    r = subprocess.run([sys.executable, str(script)], cwd=str(HERE), env=env,
                       capture_output=True, text=True, timeout=180)
    for line in r.stdout.splitlines():
        if line.startswith('PROBE_JSON '):
            return json.loads(line[len('PROBE_JSON '):]), r
    return None, r


GOOD = {'HL_LIVE_HL_ACCOUNT_ADDRESS': MASTER, 'HL_LIVE_HL_SIGNER_ADDRESS': SIGNER, 'HL_USER_WALLET': LEGACY}


def case_master_not_signer() -> None:
    out, r = run_probe(GOOD)
    if out is None:
        check('A_PROBE_RAN', False, r.stderr[-400:])
        return
    check('A_TRUTH_IS_MASTER', out['truth'] == MASTER, out['truth'])
    users = out['users']
    check('A_EVERY_TRUTH_READ_USES_MASTER', users == [MASTER], users)
    fills_users = {p.get('user') for p in out['copy_seen']}
    check('A_COPY_FILLS_USE_MASTER', fills_users == {MASTER}, fills_users)
    check('A_COPY_INGESTOR_RECEIVED_MASTER',
          fills_users == {MASTER} and out['copy_seen'], out['copy_seen'])
    types = {p.get('type') for p in out['calls']}
    check('A_FIVE_READS_EXERCISED',
          {'clearinghouseState', 'portfolio', 'userFillsByTime'} <= types, sorted(types))
    pnl_users = {p.get('user') for p in out['calls'] if p.get('type') == 'portfolio'}
    check('A_DAILY_PNL_USES_MASTER', pnl_users == {MASTER}, pnl_users)
    check('A_MARK_READ_OK', out['mark'] == 100.0, out['mark'])
    check('A_EXPOSURE_OK', (out['exposure'] or {}).get('status') == 'OK', out['exposure'])
    check('A_SNAPSHOT_OK', out['snapshot'] == 'SNAPSHOT_OK', out['snapshot'])
    check('A_DAILY_PNL_READABLE', out['daily_block'] == 'DAILY_LOSS_LIMIT_REACHED', out['daily_block'])


def case_master_equals_signer() -> None:
    out, r = run_probe({'HL_LIVE_HL_ACCOUNT_ADDRESS': MASTER, 'HL_LIVE_HL_SIGNER_ADDRESS': MASTER,
                        'HL_USER_WALLET': LEGACY})
    check('B_REFUSES_AT_PROBE', out is None or out['truth'] == '', out and out['truth'])
    if out is None:
        check('B_NO_TRACEBACK', 'Traceback' not in r.stderr, r.stderr[-400:])
        return
    check('B_EXPOSURE_HOLD', (out['exposure'] or {}).get('status') == 'COPY_ACCOUNT_NOT_CONFIGURED', out['exposure'])
    check('B_SNAPSHOT_HOLD', out['snapshot'] == 'SNAPSHOT_UNAVAILABLE', out['snapshot'])
    check('B_DAILY_PNL_HOLD', out['daily_block'] == 'DAILY_LOSS_UNREADABLE', out['daily_block'])
    check('B_COPY_FILLS_HOLD', out['copy_seen'] == [], out['copy_seen'][:3])
    check('B_NO_READ_USED_LEGACY_WALLET', LEGACY not in out['users'], out['users'])


def case_master_bad() -> None:
    for label, env_extra in (
        ('MISSING', {'HL_LIVE_HL_ACCOUNT_ADDRESS': '', 'HL_LIVE_HL_SIGNER_ADDRESS': SIGNER}),
        ('MALFORMED', {'HL_LIVE_HL_ACCOUNT_ADDRESS': '0xnothex', 'HL_LIVE_HL_SIGNER_ADDRESS': SIGNER}),
    ):
        out, r = run_probe({**env_extra, 'HL_USER_WALLET': LEGACY})
        if out is None:
            check('C_' + label + '_NO_TRACEBACK', 'Traceback' not in r.stderr, r.stderr[-400:])
            continue
        check('C_' + label + '_NO_MASTER', out['truth'] == '', out['truth'])
        check('C_' + label + '_EXPOSURE_HOLD',
              (out['exposure'] or {}).get('status') == 'COPY_ACCOUNT_NOT_CONFIGURED', out['exposure'])
        check('C_' + label + '_SNAPSHOT_HOLD', out['snapshot'] == 'SNAPSHOT_UNAVAILABLE', out['snapshot'])
        check('C_' + label + '_DAILY_PNL_HOLD', out['daily_block'] == 'DAILY_LOSS_UNREADABLE', out['daily_block'])
        check('C_' + label + '_NO_LEGACY_FALLBACK', LEGACY not in out['users'] and out['copy_seen'] == [],
              [out['users'], out['copy_seen'][:2]])


if __name__ == '__main__':
    print('ENG-INV-11 identity routing :: python ' + sys.version.split()[0])
    case_master_not_signer()
    case_master_equals_signer()
    case_master_bad()
    print('TOTAL %d  FAILED %d' % (_p + _f, _f))
    sys.exit(1 if _f else 0)
