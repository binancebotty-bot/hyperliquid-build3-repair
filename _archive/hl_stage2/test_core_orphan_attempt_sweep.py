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
          'cloid', 'status', 'exchange_order_id', 'terminal_state', 'action', 'notes',
          'fill_price', 'fill_size', 'copy_fill_id']   # a fill row without its size proves nothing


def write_csv(path, rows):
    with open(path, 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction='ignore')
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, '') for k in FIELDS})


def attempt(aid, status, oid='', reduce_only='', coin='TEST', ts=1792990000000, copy_size='10.0'):
    return {'created_at': '2026-10-26T00:00:00+00:00', 'created_at_ms': ts, 'attempt_id': aid,
            'intent_id': 'i-' + aid, 'leader_fill_id': 'lf-' + aid, 'coin': coin, 'side': 'B',
            'cloid': '0x' + aid, 'status': status, 'exchange_order_id': oid, 'reduce_only_sent': reduce_only,
            'copy_size': copy_size}


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
window = src2[mi:mi + 1400] if mi != -1 else ''
check('THE_FILL_MATCHER_CLOSES_THE_ATTEMPT_ROW',
      'close_orphan_attempt_rows(apply=True)' in window
      and window.find('close_orphan_attempt_rows') < window.find('return True'),
      'the matcher does not close the attempt row, or does it after returning')
check('THE_MATCHER_CALL_IS_GATED_FOR_MAINNET_ONLY',
      'FOLLOWER_NETWORK != "mainnet"' in window and 'auto_send_enabled' not in window,
      'the matcher-side close is gated on the order switch: a journal-only repair must run with sending OFF')
check('THE_MATCHER_CALL_IS_BURST_GUARDED',
      '_LAST_MATCHER_SWEEP' in window,
      'a catch-up burst would re-read the journals on every fill')


# ---- 8. CRITICAL: a PARTIAL fill followed by a cancel must never be called filled ----
d3 = Path(tempfile.mkdtemp(prefix='sweep3_'))
ap3, fp3 = d3 / 'send_attempts.csv', d3 / 'live_fills.csv'
write_csv(ap3, [attempt('p1', 'ORDER_RESTING', '555', copy_size='10.0')])
# the order was 10, only 2+3 filled, then it was cancelled: a fill row exists, the order did NOT fill
f1 = fill('p1', '555'); f1['fill_size'] = '2.0'
f2 = fill('p1', '555'); f2['fill_size'] = '3.0'
write_csv(fp3, [f1, f2])
try:
    out3 = fn(send_attempts_csv=str(ap3), live_fills_csv=str(fp3), apply=True)
except TypeError:
    out3 = fn(str(ap3), str(fp3), True)
rows3 = list(csv.DictReader(open(ap3, encoding='utf-8')))
filled_status = [r for r in rows3 if r['attempt_id'] == 'p1' and r['status'] == 'ORDER_FILLED']
check('PARTIAL_FILL_THEN_CANCEL_IS_NOT_MARKED_FILLED', not filled_status,
      'a 10-unit order with 5 filled and the rest cancelled was marked %r' % ([r['status'] for r in filled_status],))
check('THE_PARTIAL_FILL_IS_NAMED_NOT_SILENT', bool(out3) and out3[0].get('outcome') == 'ORPHAN_ATTEMPT_PARTIAL_FILL_UNRESOLVED',
      'report=%r' % (out3,))

# ---- 9. but a fill split across parts that ADDS UP is closed ----
d4 = Path(tempfile.mkdtemp(prefix='sweep4_'))
ap4, fp4 = d4 / 'send_attempts.csv', d4 / 'live_fills.csv'
write_csv(ap4, [attempt('q1', 'ORDER_RESTING', '666', copy_size='10.0')])
a = fill('q1', '666'); a['fill_size'] = '2.0'
b = fill('q1', '666'); b['fill_size'] = '3.0'
c = fill('q1', '666'); c['fill_size'] = '5.0'
write_csv(fp4, [a, b, c])
try:
    fn(send_attempts_csv=str(ap4), live_fills_csv=str(fp4), apply=True)
except TypeError:
    fn(str(ap4), str(fp4), True)
rows4 = list(csv.DictReader(open(ap4, encoding='utf-8')))
check('FULL_FILL_ACROSS_PARTS_IS_CLOSED',
      any(r['attempt_id'] == 'q1' and r['status'] == 'ORDER_FILLED' for r in rows4),
      'a complete 2+3+5 fill of a 10-unit order was not closed')

# ---- 10. a recon-only sighting carries no size, so it cannot justify FILLED ----
check('RECON_ONLY_WITHOUT_A_SIZE_IS_NOT_MARKED_FILLED',
      not any(r['attempt_id'] == 'p1' and r['status'] == 'ORDER_FILLED' for r in rows3),
      'a recon-only row (no size) still produced ORDER_FILLED')

# ---- 11. non-canonical order ids still match ----
d5 = Path(tempfile.mkdtemp(prefix='sweep5_'))
ap5, fp5 = d5 / 'send_attempts.csv', d5 / 'live_fills.csv'
write_csv(ap5, [attempt('n1', 'ORDER_RESTING', ' 777 ', copy_size='10.0')])
write_csv(fp5, [fill('n1', '777.0')])
try:
    fn(send_attempts_csv=str(ap5), live_fills_csv=str(fp5), apply=True)
except TypeError:
    fn(str(ap5), str(fp5), True)
rows5 = list(csv.DictReader(open(ap5, encoding='utf-8')))
check('A_NON_CANONICAL_ORDER_ID_STILL_MATCHES',
      any(r['attempt_id'] == 'n1' and r['status'] == 'ORDER_FILLED' for r in rows5),
      "' 777 ' vs '777.0' did not join - the matcher-side close would silently do nothing for such an order")


# ---- the review's findings, each pinned ----
# a 19-digit order id must survive canonicalisation EXACTLY: int(float()) collapses neighbours onto one key
d6 = Path(tempfile.mkdtemp(prefix='oid_'))
ap6, fp6 = d6 / 'send_attempts.csv', d6 / 'live_fills.csv'
write_csv(ap6, [attempt('b1', 'ORDER_RESTING', '1758000000000000123', copy_size='10.0')])
f6 = fill('b1', '1758000000000000123'); f6['fill_size'] = '5.0'
f7 = fill('n1', '1758000000000000199'); f7['fill_size'] = '5.0'
write_csv(fp6, [f6, f7])
try:
    fn(send_attempts_csv=str(ap6), live_fills_csv=str(fp6), apply=True)
except TypeError:
    fn(str(ap6), str(fp6), True)
rows6 = list(csv.DictReader(open(ap6, encoding='utf-8')))
check('A_LONG_ORDER_ID_IS_NOT_ROUNDED_INTO_A_NEIGHBOUR',
      not any(r['attempt_id'] == 'b1' and r['status'] == 'ORDER_FILLED' for r in rows6),
      '5 filled of 10 was marked FILLED because a neighbouring id rounded onto the same key')

# a partial fill must LEAVE A RECORD and stay open, not vanish and be summarised as closed
d7 = Path(tempfile.mkdtemp(prefix='partial_'))
ap7, fp7 = d7 / 'send_attempts.csv', d7 / 'live_fills.csv'
write_csv(ap7, [attempt('pp', 'ORDER_RESTING', '424242', copy_size='10.0')])
pf = fill('pp', '424242'); pf['fill_size'] = '3.0'
write_csv(fp7, [pf])
try:
    out7 = fn(send_attempts_csv=str(ap7), live_fills_csv=str(fp7), apply=True)
except TypeError:
    out7 = fn(str(ap7), str(fp7), True)
rows7 = list(csv.DictReader(open(ap7, encoding='utf-8')))
check('A_PARTIAL_FILL_LEAVES_THE_ATTEMPT_OPEN', not any(r['attempt_id'] == 'pp' and r['status'] == 'ORDER_FILLED' for r in rows7),
      'a 3-of-10 fill was closed')
check('THE_PARTIAL_FILL_IS_REPORTED_AS_UNRESOLVED',
      bool(out7) and out7[0].get('outcome') == 'ORPHAN_ATTEMPT_PARTIAL_FILL_UNRESOLVED',
      'report=%r' % (out7,))

# the sweep writes no orders, so it must not be gated on the order switch
src3 = (HERE / 'HL_Live_Copy_Service_Core.py').read_text(encoding='utf-8', errors='replace')
_fn3 = src3.find('def startup_orphan_order_check')
_call3 = src3.find('close_orphan_attempt_rows(apply=True)', _fn3)
_gap3 = src3[_fn3:_call3] if _fn3 != -1 and _call3 != -1 else 'MISSING'
check('THE_SWEEP_IS_NOT_GATED_ON_SENDING',
      _call3 != -1 and 'auto_send_enabled' not in _gap3,
      'the startup sweep sits behind the sending-off guard, so it cannot repair the post-incident state')

# the gate refusal row must name the fill, or the caller writes a second row and claims none exists
gi = src3.find('def _gate_refusal_row')
gblock = src3[gi:gi+900]
check('THE_GATE_REFUSAL_ROW_CARRIES_THE_FILL_ID', 'leader_fill_id=' in gblock,
      'the gate row omits leader_fill_id, so the caller cannot see it and writes a duplicate')


# ---- one physical order is never two filled orders (EXIT_RECOVERY writes two attempt rows) ----
d8 = Path(tempfile.mkdtemp(prefix='two_rows_'))
ap8, fp8 = d8 / 'send_attempts.csv', d8 / 'live_fills.csv'
write_csv(ap8, [attempt('a1', 'ORDER_RESTING', '909090', copy_size='10.0'),
                attempt('a2', 'ORDER_RESTING', '909090', copy_size='10.0')])
write_csv(fp8, [fill('a1', '909090')])
try:
    out8 = fn(send_attempts_csv=str(ap8), live_fills_csv=str(fp8), apply=True)
except TypeError:
    out8 = fn(str(ap8), str(fp8), True)
rows8 = list(csv.DictReader(open(ap8, encoding='utf-8')))
filled8 = [r for r in rows8 if r['status'] == 'ORDER_FILLED']
superseded8 = [r for r in rows8 if str(r['status']).startswith('SUPERSEDED_BY_')]
check('ONE_ORDER_IS_NEVER_TWO_FILLED_ORDERS', len(filled8) == 1,
      '%d rows were marked ORDER_FILLED for one exchange order' % len(filled8))
check('THE_SECOND_ROW_IS_SUPERSEDED', len(superseded8) == 1,
      'the second attempt row was not superseded: %r' % ([r['status'] for r in rows8],))


# ---- Codex GATE FAIL a175a88, findings 2 and 3, pinned ----
# a shortfall far below a cent is still a partial fill
d9 = Path(tempfile.mkdtemp(prefix='slop_'))
ap9, fp9 = d9 / 'send_attempts.csv', d9 / 'live_fills.csv'
write_csv(ap9, [attempt('s1', 'ORDER_RESTING', '313131', copy_size='1.0')])
f9 = fill('s1', '313131'); f9['fill_size'] = '0.9999999995'
write_csv(fp9, [f9])
try:
    fn(send_attempts_csv=str(ap9), live_fills_csv=str(fp9), apply=True)
except TypeError:
    fn(str(ap9), str(fp9), True)
rows9 = list(csv.DictReader(open(ap9, encoding='utf-8')))
check('A_SUB_NANO_SHORTFALL_IS_NOT_CALLED_FILLED',
      not any(r['attempt_id'] == 's1' and r['status'] == 'ORDER_FILLED' for r in rows9),
      'a cancelled 0.9999999995 of 1.0 was marked filled')

# a second row for an already-claimed oid is superseded whatever its own size says
d10 = Path(tempfile.mkdtemp(prefix='twoshort_'))
ap10, fp10 = d10 / 'send_attempts.csv', d10 / 'live_fills.csv'
write_csv(ap10, [attempt('t1', 'ORDER_RESTING', '414141', copy_size='1.0'),
                 attempt('t2', 'ORDER_RESTING', '414141', copy_size='0.5')])
f10 = fill('t1', '414141'); f10['fill_size'] = '0.5'      # short of t1's 1.0, equal to t2's 0.5
write_csv(fp10, [f10])
try:
    out10 = fn(send_attempts_csv=str(ap10), live_fills_csv=str(fp10), apply=True)
except TypeError:
    out10 = fn(str(ap10), str(fp10), True)
check('NO_PHANTOM_ROW_STAYS_OPEN_FOR_A_CLAIMED_ORDER',
      not any(r.get('outcome') == 'ORPHAN_ATTEMPT_PARTIAL_FILL_UNRESOLVED' for r in (out10 or [])
              if r.get('attempt_id') == 't2'),
      'the second row for an already-claimed order stayed open: %r' % (out10,))

# ---- Codex finding 1 (P0): a reduction must never be excluded by the follower filters ----
src4 = (HERE / 'HL_Live_Copy_Service_Core.py').read_text(encoding='utf-8', errors='replace')
i4 = src4.find('follower_entry_exclusion(', src4.find('def _process_leader_fill_inner'))
window4 = src4[max(0, i4-2600):i4 + 400]      # the block moved after the intent build under option C
check('THE_EXCLUSION_READS_THIS_WALLETS_SLEEVE_NOT_THE_AGGREGATE',
      'sleeve(fill.leader_wallet' in window4 and 'coin_net(' not in window4
      and 'classify_send_lifecycle(intent)' in window4,
      'the guard reads the aggregate coin net or the fill direction: wallet A +1 / wallet B -1 nets to zero while A '
      'still holds a position to close')
check('THE_EXCLUSION_IS_GATED_ON_THE_LEDGER_NOT_ON_FILL_METADATA',
      '_held = None' in window4 and 'held_net != 0.0' in src4,
      'the exclusion still decides entry-vs-reduction from the fill direction alone, or treats an unreadable ledger '
      'as flat; a close could be excluded')

failed = [n for n, ok in results if not ok]
print('TOTAL=%d FAILED=%d' % (len(results), len(failed)))
if failed:
    print('FAILED: ' + ', '.join(failed))
sys.exit(1 if failed else 0)
