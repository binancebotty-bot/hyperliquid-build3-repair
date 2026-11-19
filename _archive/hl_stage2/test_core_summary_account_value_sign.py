'''FAILING FIRST (D3): _summary_account_value must fail CLOSED when crossMarginSummary and
marginSummary disagree in sign. max() takes the optimistic side, overstating equity, which
loosens the liq_parity_block gate that decides whether an entry is blocked.'''
import importlib.util, os, sys

CORE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'HL_Live_Copy_Service_Core.py')
spec = importlib.util.spec_from_file_location('hl_core_avsign', CORE)
C = importlib.util.module_from_spec(spec)
sys.modules['hl_core_avsign'] = C
spec.loader.exec_module(C)

FAIL = []
def check(n, c, d=''):
    print(('PASS ' if c else 'FAIL ') + n + ((' :: ' + d) if d and not c else ''))
    if not c: FAIL.append(n)

# opposite signs: crossMarginSummary negative (the losing side), marginSummary positive
opp = {'crossMarginSummary': {'accountValue': '-5.0'},
       'marginSummary': {'accountValue': '100.0'}}
v = C._summary_account_value(opp)
check('opposite signs -> conservative (negative) value', abs(v - (-5.0)) < 1e-9, repr(v))
check('opposite signs -> return type float', isinstance(v, float), type(v).__name__)

# mirrored: conservative value is the other one, so this is not accidentally 'always first'
opp2 = {'crossMarginSummary': {'accountValue': '100.0'},
        'marginSummary': {'accountValue': '-5.0'}}
v2 = C._summary_account_value(opp2)
check('mirrored opposite signs -> conservative (negative) value', abs(v2 - (-5.0)) < 1e-9, repr(v2))

# original xyz bug must stay fixed: crossMarginSummary present but ZERO, marginSummary holds truth
xyz = {'crossMarginSummary': {'accountValue': '0.0'},
       'marginSummary': {'accountValue': '39.67'}}
check('xyz present-but-zero cross -> marginSummary truth 39.67',
      abs(C._summary_account_value(xyz) - 39.67) < 1e-6, repr(C._summary_account_value(xyz)))

# same sign: unchanged behaviour (larger value)
same = {'crossMarginSummary': {'accountValue': '10.0'}, 'marginSummary': {'accountValue': '12.5'}}
check('same sign -> larger value kept', abs(C._summary_account_value(same) - 12.5) < 1e-9,
      repr(C._summary_account_value(same)))

# shape guards unchanged
check('non-dict -> 0.0', C._summary_account_value(None) == 0.0, repr(C._summary_account_value(None)))
check('no summaries -> 0.0', C._summary_account_value({}) == 0.0, repr(C._summary_account_value({})))

print('\nFAILED: %d' % len(FAIL))
sys.exit(1 if FAIL else 0)
