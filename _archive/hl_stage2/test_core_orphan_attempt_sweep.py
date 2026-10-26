#!/usr/bin/env python3
"""The missing terminal write: a fill that arrives after placement must close its attempt row.

Root cause (proved in 6411147014): `send_attempts.csv` is only ever closed out by the immediate placement
response (Core:5527) or by a retry supersede (Core:6134). Orders that rest and fill LATER are learned by the fill
matcher (Core:10595-10632), which writes live_fills + reconciliation `COPY_FILL/MATCHED_BY_EXCHANGE_ORDER_ID` and
never calls `update_send_attempt_row`. So the outcome exists in one table and not the other - which is why the
ledger is exact while the journal says ORDER_RESTING, and why the two EXIT_RECOVERY closes stayed at
`pending_send` forever.

The sweep adds the missing edge and nothing else. Constraints (ruling 6410997129):
  (a) idempotent - exactly one terminal row per attempt, never a second for one already terminal
  (b) the outcome comes from EXCHANGE data the engine already persisted (live_fills / COPY_FILL by
      exchange_order_id), never from "not in openOrders"
  (c) no new endpoint load: zero HTTP calls, extra weight 0
  (d) it only writes journal rows: no place, cancel, modify, mode change or ledger touch
  (e) closes first, and every retirement emits an alert row

FAILING FIRST on eba4bde: there is no sweep, so a resting fill leaves its attempt row at ORDER_RESTING/pending_send.
"""
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import HL_Live_Copy_Service_Core as C  # noqa: E402

results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print('RESULT::%s_%s%s' % (name, 'PASS' if ok else 'FAIL', (' | ' + str(detail)[:220]) if not ok else ''))


def have(name):
    return hasattr(C, name) or hasattr(C.LiveCopyCore, name) if hasattr(C, 'LiveCopyCore') else hasattr(C, name)


SWEEP = 'close_orphan_attempt_rows'
exists = hasattr(C, SWEEP) or (hasattr(C, 'LiveCopyCore') and hasattr(C.LiveCopyCore, '_close_orphan_attempt_rows'))

if not exists:
    for name in ('RESTING_FILLED_CLOSES_THE_ATTEMPT_ROW',
                 'RESTING_CANCELLED_IS_NOT_MARKED_FILLED',
                 'A_CLOSE_NEVER_MARKED_SENT_IS_RETIRED_FIRST',
                 'AN_ALREADY_TERMINAL_ATTEMPT_IS_NOT_TOUCHED',
                 'THE_SWEEP_MAKES_NO_EXCHANGE_CALL'):
        check(name, False, 'no sweep exists on this build - the attempt row is never closed after a later fill')
    print('TOTAL=5 FAILED=5')
    sys.exit(1)

# The sweep must be a module-level function so it can be tested without an engine, and it must take its paths as
# arguments so a test never writes the live journal.
fn = getattr(C, SWEEP, None) or C.LiveCopyCore._close_orphan_attempt_rows
import inspect
sig = inspect.signature(fn)
params = list(sig.parameters)
check('THE_SWEEP_TAKES_ITS_INPUT_PATHS',
      any('attempts' in p for p in params) and any('fill' in p or 'recon' in p for p in params),
      'signature is %s - a test could not run it against its own files' % (params,))

import csv
import tempfile

FIELDS = ['created_at', 'created_at_ms', 'attempt_id', 'intent_id', 'leader_fill_id', 'leader_wallet', 'coin',
          'side', 'order_type', 'limit_price', 'copy_size', 'copy_notional', 'reduce_only_sent', 'sleeve_id',
          'cloid', 'status', 'exchange_order_id', 'terminal_state', 'action', 'notes']


def write_csv(path, rows):
    with open(path, 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction='ignore')
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, '') for k in FIELDS})


def attempt(aid, status, oid='', reduce_only='', coin='TEST', ts=1792990000000):
    return {'created_at': '2026-10-26T00:00:00+00:00', 'created_at_ms': ts, 'attempt_id': aid,
            'intent_id': 'i-' + aid, 'leader_fill_id': 'lf-' + aid, 'coin': coin, 'side': 'B',
            'cloid': '0x' + aid, 'status': status, 'exchange_order_id': oid, 'reduce_only_sent': reduce_only}


def fill(aid, oid, coin='TEST'):
    # live_fills row: the exchange's own fill data, as the engine persisted it
    return {'created_at': '2026-10-26T00:01:00+00:00', 'created_at_ms': 1792991000000, 'copy_fill_id': 'cf-' + aid,
            'exchange_order_id': oid, 'coin': coin, 'fill_price': '1.0', 'fill_size': '10.0',
            'notes': 'matched by exchange_order_id=%s; MATCHED_BY_EXCHANGE_ORDER_ID' % oid}


def run_sweep(attempts, fills):
    d = Path(tempfile.mkdtemp(prefix='sweep_'))
    ap, fp = d / 'send_attempts.csv', d / 'live_fills.csv'
    write_csv(ap, attempts)
    write_csv(fp, fills)
    try:
        out = fn(send_attempts_csv=str(ap), live_fills_csv=str(fp), apply=True)
    except TypeError:
        out = fn(str(ap), str(fp), True)
    rows = list(csv.DictReader(open(ap, encoding='utf-8')))
    return out, rows


# ---- 1. a resting fill closes the attempt row, once ----
out, rows = run_sweep([attempt('r1', 'ORDER_RESTING', '999')], [fill('r1', '999')])
closed = [r for r in rows if r['attempt_id'] == 'r1' and r['status'] in ('ORDER_FILLED', 'MATCHED_BY_EXCHANGE_ORDER_ID')]
check('RESTING_FILLED_CLOSES_THE_ATTEMPT_ROW', len(closed) == 1,
      'rows for r1 = %r' % ([(r['status'], r['terminal_state']) for r in rows if r['attempt_id'] == 'r1'],))

# ---- 2. a resting order with NO fill must not be marked filled ----
out, rows = run_sweep([attempt('c1', 'ORDER_RESTING', '888')], [])
touched = [r for r in rows if r['attempt_id'] == 'c1' and r['status'] not in ('ORDER_RESTING',)]
check('RESTING_CANCELLED_IS_NOT_MARKED_FILLED', not touched,
      'an unfilled resting order was changed: %r' % ([(r['status'], r['terminal_state']) for r in touched],))

# ---- 3. closes are retired before entries ----
out, rows = run_sweep(
    [attempt('e1', 'ORDER_RESTING', '111', ts=1792990000100), attempt('x1', 'pending_send', '222', reduce_only='True', ts=1792990000200)],
    [fill('e1', '111'), fill('x1', '222')])
# the ORDER of retirements is what this asserts; the attempt row's action column is not guaranteed to exist
first_id = out[0]['attempt_id'] if out else None
check('A_CLOSE_NEVER_MARKED_SENT_IS_RETIRED_FIRST', first_id == 'x1',
      'the first retirement was %r (report=%r), expected the reduce-only close x1' % (first_id, out))

# ---- 4. an already-terminal attempt is not touched ----
out, rows = run_sweep([attempt('t1', 'ORDER_FILLED', '333')], [fill('t1', '333')])
extra = [r for r in rows if r['attempt_id'] == 't1']
check('AN_ALREADY_TERMINAL_ATTEMPT_IS_NOT_TOUCHED', len(extra) == 1,
      'a terminal attempt gained %d extra row(s)' % (len(extra) - 1))

# ---- 5. no exchange call: the sweep's source is our own persisted exchange data ----
src = (HERE / 'HL_Live_Copy_Service_Core.py').read_text(encoding='utf-8', errors='replace')
body = src[src.find('def close_orphan_attempt_rows'):]
body = body[:body.find('\ndef ', 10)] if '\ndef ' in body[10:] else body
check('THE_SWEEP_MAKES_NO_EXCHANGE_CALL', not any(t in body for t in ('requests.', 'urllib', 'post_many', '_XNET')),
      'the sweep body references an HTTP path')


# ---- 6. the LIVE fill path closes only the order it matched (source fix, not just the startup sweep) ----
d2 = Path(tempfile.mkdtemp(prefix='sweep2_'))
ap2, fp2 = d2 / 'send_attempts.csv', d2 / 'live_fills.csv'
write_csv(ap2, [attempt('m1', 'ORDER_RESTING', '111'), attempt('m2', 'ORDER_RESTING', '222')])
write_csv(fp2, [fill('m1', '111'), fill('m2', '222')])
try:
    out2 = fn(send_attempts_csv=str(ap2), live_fills_csv=str(fp2), only_oid='111', apply=True)
except TypeError:
    out2 = fn(str(ap2), str(fp2), True, '111')
rows2 = list(csv.DictReader(open(ap2, encoding='utf-8')))
closed_ids = {r['attempt_id'] for r in rows2 if r['status'] == 'ORDER_FILLED'}
check('THE_MATCHER_CLOSES_ONLY_THE_ORDER_IT_MATCHED', closed_ids == {'m1'},
      'closed %r - only the matched order (111 / m1) may be closed' % (closed_ids,))

# ---- 7. and the matcher really calls it, above its return ----
src2 = (HERE / 'HL_Live_Copy_Service_Core.py').read_text(encoding='utf-8', errors='replace')
mi = src2.find('recovered from send_attempt')
window = src2[mi:mi + 900] if mi != -1 else ''
check('THE_FILL_MATCHER_CLOSES_THE_ATTEMPT_ROW', 'close_orphan_attempt_rows(only_oid=norm_oid' in window
      and window.find('close_orphan_attempt_rows') < window.find('return True'),
      'the matcher does not close the attempt row, or does it after returning')

failed = [n for n, ok in results if not ok]
print('TOTAL=%d FAILED=%d' % (len(results), len(failed)))
if failed:
    print('FAILED: ' + ', '.join(failed))
sys.exit(1 if failed else 0)
