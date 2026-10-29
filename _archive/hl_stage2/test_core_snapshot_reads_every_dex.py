"""FAILING FIRST (controller 6431520668 item 2): fetch_snapshot posts clearinghouseState with
NO dex, so exchange_account_snapshot.json only ever holds the default dex. Positions and equity
held on a HIP-3 dex (xyz) are invisible to it."""
import importlib.util, json, os, sys, tempfile, types

CORE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'HL_Live_Copy_Service_Core.py')
spec = importlib.util.spec_from_file_location('hl_core_dex', CORE)
C = importlib.util.module_from_spec(spec)
sys.modules['hl_core_dex'] = C
spec.loader.exec_module(C)

FAIL = []
CASES = []
def check(n, c, d=''):
    print(('PASS ' if c else 'FAIL ') + n + ((' :: ' + d) if d and not c else ''))
    CASES.append(n)
    if not c: FAIL.append(n)

CALLS = []

class FakeResp:
    def __init__(self, payload): self._p = payload
    def json(self): return self._p

def fake_post(url, json=None, timeout=None):
    body = dict(json or {})
    CALLS.append(body)
    dex = body.get('dex') or ''
    if dex == 'xyz':
        return FakeResp({'marginSummary': {'accountValue': '39.67'},
                         'crossMarginSummary': {'accountValue': '0.0'},
                         'assetPositions': []})
    return FakeResp({'marginSummary': {'accountValue': '100.0'},
                     'crossMarginSummary': {'accountValue': '100.0'},
                     'assetPositions': []})

class FakeRequests:
    post = staticmethod(fake_post)

C.requests = FakeRequests
C.USER_WALLET = '0x7ae3b08bb4e7b085c6db5d635b96bec9715e9205'
C._LEARNED_DEXES = set(['xyz'])
C._follower_dex_names = lambda: None
tmp = tempfile.mkdtemp(prefix='dex_snap_')
import pathlib
C.AUDIT_DIR = pathlib.Path(tmp)
C.EXCHANGE_ACCOUNT_SNAPSHOT_FILE = C.AUDIT_DIR / 'exchange_account_snapshot.json'

rec = C.ExchangeReconciler(types.SimpleNamespace(), types.SimpleNamespace())
snap, status = rec.fetch_snapshot()

check('fetch returned SNAPSHOT_OK', status == 'SNAPSHOT_OK', status)
dexes_requested = [c.get('dex') or '' for c in CALLS]
check('a clearinghouseState call was made for the xyz dex', 'xyz' in dexes_requested, str(dexes_requested))
check('the default dex is still read', '' in dexes_requested, str(dexes_requested))
check('every call is a SINGLE object (the endpoint rejects arrays)',
      all(isinstance(c, dict) for c in CALLS), 'array payload shipped')

raw_by_dex = snap.get('raw_by_dex') if isinstance(snap, dict) else None
check('snapshot keeps a per-dex raw map', isinstance(raw_by_dex, dict) and raw_by_dex, repr(type(raw_by_dex)))
if isinstance(raw_by_dex, dict):
    check('raw_by_dex has the default dex', '' in raw_by_dex, str(list(raw_by_dex)))
    check('raw_by_dex has the xyz dex', 'xyz' in raw_by_dex, str(list(raw_by_dex)))
    check('xyz raw carries the real 39.67',
          abs(C._summary_account_value(raw_by_dex.get('xyz', {})) - 39.67) < 1e-6,
          repr(raw_by_dex.get('xyz')))
check('raw still present for the default dex (back-compat)', isinstance(snap.get('raw'), dict) and snap['raw'], 'missing raw')

print('TOTAL=%d FAILED=%d' % (len(CASES), len(FAIL)))
sys.exit(1 if FAIL else 0)
