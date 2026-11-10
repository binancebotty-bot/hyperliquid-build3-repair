#!/usr/bin/env python3
"""A missed-entry rejection must say WHY in its structured fields.

Run 13 (2026-10-26) produced 9 rows with `terminal_state=MISSED_ENTRY_DIFF_LIMIT_REJECTED` and an EMPTY
`reject_category`, empty `operator_action` and empty `exchange_response` - the exchange's message survived
only in free text, so nothing could group, count or alert on the cause. The controller ordered the fields
filled on that path (6407488905).

Two things are asserted, and the difference matters:
  * the CLASSIFIERS, behaviourally, with the exchange's real rejection strings - so a halted market is
    provably classified MARKET_HALTED rather than left blank;
  * that the missed-entry path's row update actually WRITES those three fields (structural: the call site
    inside `_missed_entry_rest_or_diff`). Driving that whole path end-to-end needs the resolver, the
    exchange client, margin setup and a live audit, and a stub of all that would test the stub.
"""
import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import HL_Live_Copy_Service_Core as C  # noqa: E402

SRC = (HERE / 'HL_Live_Copy_Service_Core.py').read_text(encoding='utf-8-sig', errors='replace')
results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print('RESULT::%s_%s%s' % (name, 'PASS' if ok else 'FAIL', (' | ' + str(detail)[:180]) if not ok else ''))


HALTED_REPLY = {"status": "ok", "response": {"type": "order", "data": {"statuses": [{"error": "Trading is halted."}]}}}
IOC_REPLY = {"status": "ok", "response": {"type": "order",
                                          "data": {"statuses": [{"error": "Order could not immediately match against any resting orders."}]}}}

cat_halted = C.classify_reject_category("Trading is halted.", HALTED_REPLY)
check('HALTED_MARKET_IS_CLASSIFIED', cat_halted == 'MARKET_HALTED', 'got %r' % (cat_halted,))

cat_ioc = C.classify_reject_category("Order could not immediately match against any resting orders.", IOC_REPLY)
check('IOC_NO_MATCH_IS_CLASSIFIED', cat_ioc == 'IOC_NO_IMMEDIATE_MATCH', 'got %r' % (cat_ioc,))

lifecycle = 'ENTRY'
act_halted = C.classify_operator_action('ORDER_REJECTED', cat_halted, lifecycle, True)
check('A_HALTED_REJECTION_HAS_A_NAMED_OPERATOR_ACTION', bool((act_halted or '').strip()), 'got %r' % (act_halted,))

# the structural half: the update_send_attempt_row call inside the missed-entry path writes the fields
fn = None
for node in ast.walk(ast.parse(SRC)):
    if isinstance(node, ast.FunctionDef) and node.name == '_missed_entry_rest_or_diff':
        fn = node
        break
check('THE_MISSED_ENTRY_PATH_EXISTS', fn is not None)

fields = set()
if fn is not None:
    for node in ast.walk(fn):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == 'update_send_attempt_row' and len(node.args) >= 2
                and isinstance(node.args[1], ast.Dict)):
            for key in node.args[1].keys:
                if isinstance(key, ast.Constant):
                    fields.add(key.value)

check('MISSED_ENTRY_ROW_WRITES_REJECT_CATEGORY', 'reject_category' in fields, sorted(fields))
check('MISSED_ENTRY_ROW_WRITES_OPERATOR_ACTION', 'operator_action' in fields, sorted(fields))
check('MISSED_ENTRY_ROW_WRITES_EXCHANGE_RESPONSE', 'exchange_response' in fields, sorted(fields))

failed = [n for n, ok in results if not ok]
print('TOTAL=%d FAILED=%d' % (len(results), len(failed)))
if failed:
    print('FAILED: ' + ', '.join(failed))
sys.exit(1 if failed else 0)
