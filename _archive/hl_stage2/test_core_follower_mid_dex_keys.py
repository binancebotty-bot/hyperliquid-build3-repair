'''FAILING FIRST (controller 6435314214): D2's namespacing landed in _fetch_all_mids only. follower_mid
(the price gate for every xyz/HIP-3 copy) still writes every DEX's mids into ONE dict with BARE keys and
looks the caller's coin up bare. Consequences, both live on this path:
  - follower_mid('xyz:AMD') returned 0.0 - the namespaced key is never written;
  - a bare key from a named DEX overwrote the default DEX's price for the same symbol.
Measured 2026-10-27 on testnet: the exchange already prefixes non-default mids ('xyz:AAPL'); a bare name
from a named DEX must still be prefixed on write or it collides.

CORE_PATH=<pristine core> proves RED.
'''
import importlib.util, os, sys

CORE = os.environ.get('CORE_PATH') or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'HL_Live_Copy_Service_Core.py')
spec = importlib.util.spec_from_file_location('hl_core_fmid', CORE)
C = importlib.util.module_from_spec(spec)
sys.modules['hl_core_fmid'] = C
spec.loader.exec_module(C)

FAIL = []
CASES = []


def check(n, c, d=''):
    print(('PASS ' if c else 'FAIL ') + n + ((' :: ' + d) if d and not c else ''))
    CASES.append(n)
    if not c:
        FAIL.append(n)


PAYLOADS = {
    '': {'AMD': '100.0', '#102170': '0.5'},
    'xyz': {'AMD': '581.08', 'xyz:AAPL': '342.59'},
}


def fake_post_many(fetcher, payloads, *a, **k):
    out = []
    for p in payloads:
        dex = p.get('dex') or ''
        out.append({'ok': True, 'data': dict(PAYLOADS.get(dex, {}))})
    return out


C._XNET.post_many = fake_post_many
C.follower_dex_scope = lambda: ['', 'xyz']


def mid(coin):
    C._FOLLOWER_MIDS.update(px={}, ms=0, scope=None)   # force one fresh read per check
    return C.follower_mid(coin)


check('follower_mid resolves a namespaced xyz coin', mid('xyz:AMD') == 581.08, str(mid('xyz:AMD')))
check('a bare key from a named DEX does not overwrite the default DEX price',
      mid('AMD') == 100.0, str(mid('AMD')))
check('a bare key from a named DEX is stored namespaced',
      C._FOLLOWER_MIDS['px'].get('XYZ:AMD') == 581.08, str(sorted(C._FOLLOWER_MIDS['px'])))
check('an already-prefixed key is not double-prefixed',
      'XYZ:XYZ:AAPL' not in C._FOLLOWER_MIDS['px'], str(sorted(C._FOLLOWER_MIDS['px'])))
check('an already-prefixed key carries the named DEX price', mid('xyz:AAPL') == 342.59, str(mid('xyz:AAPL')))
check('a numbered default mid is untouched', mid('#102170') == 0.5, str(mid('#102170')))

# The leader path reads the same allMids shape into its own bare dict: same collision, same helper.
C._LEADER_MIDS.update(px={}, ms=0, dexes=[])
check('leader_mid resolves a namespaced xyz coin', C.leader_mid('xyz:AMD') == 581.08, str(C.leader_mid('xyz:AMD')))
C._LEADER_MIDS.update(px={}, ms=0, dexes=[])
check('leader_mid keeps the default DEX price bare', C.leader_mid('AMD') == 100.0, str(C.leader_mid('AMD')))

print('TOTAL=%d FAILED=%d' % (len(CASES), len(FAIL)))
sys.exit(1 if FAIL else 0)
