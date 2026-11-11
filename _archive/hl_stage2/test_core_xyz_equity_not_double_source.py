"""FAILING FIRST (controller 6431520668 item 1): on the xyz dex `crossMarginSummary` is a
PRESENT-BUT-ZERO dict, so `raw.get("crossMarginSummary") or raw.get("marginSummary")` never
falls through and per-dex equity reads 0.0 instead of the real isolated-margin value.
"""
import importlib.util, json, os, sys, tempfile

CORE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'HL_Live_Copy_Service_Core.py')
spec = importlib.util.spec_from_file_location('hl_core_xyz', CORE)
C = importlib.util.module_from_spec(spec)
sys.modules['hl_core_xyz'] = C
spec.loader.exec_module(C)

FAIL = []
def check(name, cond, detail=''):
    print(('PASS ' if cond else 'FAIL ') + name + ((' :: ' + detail) if detail and not cond else ''))
    if not cond: FAIL.append(name)

def xyz_snapshot():
    return {'raw': {'marginSummary': {'accountValue': '39.670000', 'totalNtlPos': '0.0', 'totalRawUsd': '39.67', 'totalMarginUsed': '0.0'},
                    'crossMarginSummary': {'accountValue': '0.0', 'totalNtlPos': '0.0', 'totalRawUsd': '0.0', 'totalMarginUsed': '0.0'},
                    'crossMaintenanceMarginUsed': '0.0', 'assetPositions': [], 'withdrawable': '39.67'},
            'dex': 'xyz'}

def run():
    tmp = tempfile.mkdtemp(prefix='xyz_eq_')
    try:
        C.AUDIT_DIR = __import__('pathlib').Path(tmp)
    except Exception:
        C.AUDIT_DIR = tmp
    hist = os.path.join(tmp, 'exchange_account_history.json')
    wrote = C.append_account_history_point(xyz_snapshot())
    check('xyz snapshot is recorded (not dropped as zero account)', wrote is True, 'append returned %r' % (wrote,))
    data = []
    if os.path.exists(hist):
        data = json.load(open(hist, encoding='utf-8'))
    check('history has exactly one point', len(data) == 1, 'len=%d' % len(data))
    if data:
        v = float(data[-1].get('account_value') or data[-1].get('value') or 0.0)
        check('recorded equity is 39.67 not 0.0', abs(v - 39.67) < 1e-6, 'got %r' % (v,))
    print('\nFAILED: %d' % len(FAIL))
    return 1 if FAIL else 0

if __name__ == '__main__':
    sys.exit(run())
