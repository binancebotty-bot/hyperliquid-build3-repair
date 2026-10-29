'''FAILING FIRST (D2): a non-default DEX mid was written as a bare string, so two DEXes returning the
same bare name overwrite each other and a namespaced lookup (`xyz:AMD`, the sdk_coin shape) never
matches. Measured 2026-10-27 on testnet: the exchange already prefixes non-default mids
(`xyz:AAPL`); a bare name from a named DEX must be prefixed on write or it collides.

CORE_PATH=<pristine core> proves RED.
'''
import importlib.util, os, sys

CORE = os.environ.get('CORE_PATH') or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'HL_Live_Copy_Service_Core.py')
spec = importlib.util.spec_from_file_location('hl_core_midk', CORE)
C = importlib.util.module_from_spec(spec)
sys.modules['hl_core_midk'] = C
spec.loader.exec_module(C)

FAIL = []
CASES = []


def check(n, c, d=''):
    print(('PASS ' if c else 'FAIL ') + n + ((' :: ' + d) if d and not c else ''))
    CASES.append(n)
    if not c:
        FAIL.append(n)


class FakeResp:
    def __init__(self, payload):
        self._p = payload

    def json(self):
        return self._p


PAYLOADS = {
    '': {'AMD': '100.0', '#102170': '0.5'},
    'xyz': {'AMD': '581.08', 'xyz:AAPL': '342.59'},
}


def fake_post(url, json=None, timeout=None):
    return FakeResp(PAYLOADS.get((json or {}).get('dex') or '', {}))


C.requests = type('R', (), {'post': staticmethod(fake_post)})
C._LEARNED_DEXES = {'xyz'}


class Obj:
    _mids_cache = None
    _mids_fetched_ms = 0


mids = C.SenderGateway._fetch_all_mids(Obj())
check('named DEX bare mid is namespaced', 'XYZ:AMD' in mids, str(sorted(mids)))
check('default DEX bare mid kept bare', mids.get('AMD') == 100.0, str(mids.get('AMD')))
check('namespaced mid carries the named DEX price', mids.get('XYZ:AMD') == 581.08, str(mids.get('XYZ:AMD')))
check('already-prefixed key not double-prefixed', 'XYZ:XYZ:AAPL' not in mids, str(sorted(mids)))
check('already-prefixed key survives', mids.get('XYZ:AAPL') == 342.59, str(mids.get('XYZ:AAPL')))
check('numbered default mid untouched', mids.get('#102170') == 0.5, str(mids.get('#102170')))

Obj._mids_cache = mids
check('reader resolves xyz:AMD', C.SenderGateway._reference_price(Obj(), 'xyz:AMD') == 581.08,
      str(C.SenderGateway._reference_price(Obj(), 'xyz:AMD')))
check('reader resolves bare AMD to the default DEX', C.SenderGateway._reference_price(Obj(), 'AMD') == 100.0,
      str(C.SenderGateway._reference_price(Obj(), 'AMD')))

print('TOTAL=%d FAILED=%d' % (len(CASES), len(FAIL)))
sys.exit(1 if FAIL else 0)
