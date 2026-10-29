'''FAILING FIRST (D1): _fetch_all_mids wraps the whole per-dex loop in one try/except, so one
failing dex aborts the remaining dexes AND caches the partial map. Each dex must be isolated and
the failure logged through log_error (the module's own facility), naming the dex.'''
import importlib.util, os, pathlib, sys, tempfile, types

CORE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'HL_Live_Copy_Service_Core.py')
spec = importlib.util.spec_from_file_location('hl_core_midsdex', CORE)
C = importlib.util.module_from_spec(spec)
sys.modules['hl_core_midsdex'] = C
spec.loader.exec_module(C)

FAIL = []
def check(n, c, d=''):
    print(('PASS ' if c else 'FAIL ') + n + ((' :: ' + d) if d and not c else ''))
    if not c: FAIL.append(n)

CALLS, LOGGED = [], []

class FakeResp:
    def __init__(self, payload): self._p = payload
    def json(self): return self._p

def fake_post(url, json=None, timeout=None):
    dex = (json or {}).get('dex') or ''
    CALLS.append(dex)
    if dex == 'd2':
        raise ConnectionError('d2 boom')
    coin = {'': 'BTC', 'd3': 'XYZ'}.get(dex, 'OTHER')
    return FakeResp({coin: '123.5'})

C.requests = types.SimpleNamespace(post=fake_post)   # plain function, not a bound method
C._LEARNED_DEXES = {'d2', 'd3'}
C._follower_dex_names = lambda: None
C.log_error = lambda context, exc: LOGGED.append((context, exc))
C.AUDIT_DIR = C.APPEND_ONLY_DIR = pathlib.Path(tempfile.mkdtemp(prefix='midsdex_'))
C.HL_INFO_URL = 'https://api.hyperliquid.xyz/info'

gw = C.SenderGateway(C.ConfigManager(), C.AuditLogWriter())
mids = gw._fetch_all_mids()

check('the dex after the failing one is still read', 'd3' in CALLS, str(CALLS))
check('the failing dex does not abort the loop', CALLS[:3] == ['', 'd2', 'd3'], str(CALLS))
check('mids from the dex before the failure land', mids.get('BTC') == 123.5, repr(mids))
check('mids from the dex AFTER the failure land', mids.get('D3:XYZ') == 123.5, repr(mids))
check('the cache holds the successful dexes', gw._mids_cache.get('D3:XYZ') == 123.5, repr(gw._mids_cache))
check('second read is served from the cache (no extra call)', CALLS.count('d3') == 1, str(CALLS))

check('the failure was logged through log_error', len(LOGGED) == 1, repr(LOGGED))
if LOGGED:
    ctx, exc = LOGGED[0]
    check('log names the failing dex', 'd2' in str(ctx), repr(ctx))
    check('log carries the exception', isinstance(exc, BaseException) and 'boom' in str(exc), repr(exc))

print('\nFAILED: %d' % len(FAIL))
sys.exit(1 if FAIL else 0)
