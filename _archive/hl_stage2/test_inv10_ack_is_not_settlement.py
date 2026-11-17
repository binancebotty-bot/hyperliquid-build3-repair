"""ENG-INV-10 offline instrument: an API acknowledgement is NOT settlement.

Requirement (ARCH inv10 / CONTROL_STATE required_semantics[5]): a physical send is settled only
after the engine reads MASTER truth (clearinghouseState / userFillsByTime) itself. An exchange
reply of ok/resting/filled is evidence of an ACK, never of a position.

Everything here is offline: the /info HTTP layer is an injected fetcher double and the exchange
order call is an injected double, so no socket is opened and no order exists. Each case asserts
the ABSENCE of the wrong conclusion (no settled terminal, no adopted position) as well as the
presence of the right one.

Run:
    cd _archive/hl_stage2 && HL_LIVE_ENV_FILE=/nonexistent python -u test_inv10_ack_is_not_settlement.py
"""
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
_SCRATCH = os.environ.get('TMPDIR') or tempfile.gettempdir()
sys.path.insert(0, str(HERE))
os.environ['HL_LIVE_ENV_FILE'] = '/nonexistent'   # never load live credentials
os.environ['HL_LIVE_AUDIT_DIR'] = tempfile.mkdtemp(prefix='inv10_boot_', dir=_SCRATCH)
os.environ.pop('HL_LIVE_HL_PRIVATE_KEY', None)    # no real sender in this instrument

import exchange_truth as X            # noqa: E402
import HL_Live_Copy_Service as svc    # noqa: E402

MASTER = '0x' + 'a' * 40
SIGNER = '0x' + 'b' * 40
COIN = 'ETH'
WALLET = '0xw1'

STATS = {'pass': 0, 'fail': 0}


def check(name, ok, detail=''):
    if ok:
        STATS['pass'] += 1
        print('RESULT::PASS::' + name)
    else:
        STATS['fail'] += 1
        print('RESULT::FAIL::' + name + '::' + str(detail).replace('\n', ' ')[:400])


class FakeInfo:
    """Offline /info double: perpDexs + clearinghouseState + userFillsByTime + openOrders."""

    def __init__(self, positions=None, fills=None, open_orders=None):
        self.positions = dict(positions or {})
        self.fills = list(fills or [])
        self.open_orders = list(open_orders or [])
        self.calls = []

    def __call__(self, payload):
        self.calls.append(dict(payload))
        kind = payload.get('type')
        if kind == 'perpDexs':
            return []
        if kind == 'clearinghouseState':
            return {'assetPositions': [{'position': {'coin': c, 'szi': str(s)}}
                                       for c, s in self.positions.items()]}
        if kind == 'userFillsByTime':
            return list(self.fills)
        if kind == 'openOrders':
            return list(self.open_orders)
        raise RuntimeError('unexpected /info payload: ' + str(kind))


def fresh_case():
    """A private audit folder per case so no artifact can leak between cases."""
    tmp = Path(tempfile.mkdtemp(prefix='inv10_case_', dir=_SCRATCH))
    (tmp / 'live_config.json').write_text(json.dumps({'wallets': {
        WALLET: {'mode': 'LIVE', 'enabled': True, 'copy_mode': 'proportional',
                 'norm_base': 100.0, 'leader_equity_base': 1000.0,
                 'max_manual_order_notional_usd': 25.0}}}), encoding='utf-8')
    svc.configure_paths(tmp, tmp / 'raw_live_fills.csv')
    return tmp


def wire_master(fetcher):
    svc.MASTER_TRUTH_ADDRESS, svc.MASTER_TRUTH_SIGNER = MASTER, SIGNER
    svc.MASTER_TRUTH_FETCHER, svc.MASTER_TRUTH_DEXES = fetcher, ['']
    svc.UNATTRIBUTED_INVENTORY.clear()


def fake_exchange(raw_ack=None, timeout=False):
    """The exchange order authority double. A real HL ack goes through the engine's OWN parser."""
    calls = []

    def sender(payload, marketable_bps=0.0, use_current_quote=False, max_notional=None):
        calls.append({'coin': payload.get('coin'), 'side': payload.get('side'),
                      'size': payload.get('copy_size')})
        if timeout:
            return {'ok': False, 'status': 'ORDER_UNKNOWN', 'coin': COIN,
                    'error': 'exchange timeout: no acknowledgement'}
        parsed = svc.parse_hl_order_status(raw_ack)
        return {'ok': bool(parsed.get('ok')), 'status': parsed.get('status'),
                'oid': parsed.get('oid', ''), 'fill_size': parsed.get('fill_size', ''),
                'error': parsed.get('error', ''), 'coin': COIN,
                'side': payload.get('side'), 'size': payload.get('copy_size')}

    sender.calls = calls
    return sender


def write_would_send(intent_id, side='BUY', size=0.008, price=2500.0):
    svc.ensure_csv_schema(svc.WOULD_SEND_ORDERS_CSV, svc.WOULD_SEND_ORDER_FIELDS)
    svc.append_csv(svc.WOULD_SEND_ORDERS_CSV, svc.WOULD_SEND_ORDER_FIELDS, {
        'created_at': svc.utc_now_iso(), 'dry_run': True, 'intent_id': intent_id,
        'leader_wallet': WALLET, 'leader_fill_id': 'LF-' + intent_id,
        'source_reason': 'LIVE_WS_DETECTED', 'execution_decision': 'WOULD_PLACE_IOC_LIMIT',
        'decision_reason': 'COPY_FILL', 'coin': COIN, 'side': side,
        'copy_size': size, 'copy_notional': round(size * price, 8),
        'order_type': 'IOC_LIMIT', 'limit_price': price, 'reduce_only': False,
        'manual_reconcile_required': '', 'status': 'WOULD_SEND_DRY_RUN',
        'notes': 'ENG-INV-10 fixture',
    })
    return intent_id


def read_json(path):
    p = Path(path)
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}


def attempt_rows(intent_id):
    p = Path(svc.SEND_ATTEMPTS_CSV)
    if not p.exists():
        return []
    with p.open(encoding='utf-8', newline='') as fh:
        return [r for r in csv.DictReader(fh) if r.get('intent_id') == intent_id]


def snapshot():
    st = read_json(svc.SERVICE_STATE_FILE)
    rec = (st.get('in_flight_unresolved') or {}).get(COIN) or {}
    terms = st.get('in_flight_terminals') or {}
    pos = read_json(svc.MANUAL_LIVE_POSITIONS_FILE)
    return rec, terms, pos


def quote(tag, obj):
    print('RESULT::ROW::' + tag + '=' + json.dumps(obj, sort_keys=True, default=str))


# ---------------------------------------------------------------- S1
def case_s1():
    fresh_case()
    fetcher = FakeInfo()                       # MASTER flat, no fills
    wire_master(fetcher)
    sender = fake_exchange({'status': 'ok', 'response': {'data': {'statuses': [{'resting': {'oid': 9001}}]}}})
    svc.send_hyperliquid_order = sender
    iid = write_would_send('INV10-S1')
    svc.manual_send_one_intent(iid, True)
    rows = attempt_rows(iid)
    row = rows[-1] if rows else {}
    rec, terms, pos = snapshot()
    quote('S1 send_attempts row', {k: row.get(k) for k in ('status', 'coin', 'side', 'copy_size', 'confirmed')})
    quote('S1 in_flight_unresolved[' + COIN + ']', rec)
    quote('S1 in_flight_terminals', terms)
    check('S1 ack recorded as ORDER_RESTING, not filled', row.get('status') == 'ORDER_RESTING', repr(row.get('status')))
    check('S1 no filled send_attempts terminal state', str(row.get('status') or '').upper() not in
          {'ORDER_FILLED', 'FILLED', 'SETTLED_FULL'}, repr(row.get('status')))
    check('S1 no settled ledger row (in_flight_terminals has no ' + COIN + ')', COIN not in terms, json.dumps(terms))
    check('S1 reservation still blocking (settlement not granted)', COIN in (rec and {COIN: rec} or {}), json.dumps(rec))
    check('S1 MASTER flat => no position recorded', COIN not in pos, json.dumps(pos))
    check('S1 exactly one physical send attempted', len(sender.calls) == 1, str(len(sender.calls)))


# ---------------------------------------------------------------- S2
def case_s2():
    fresh_case()
    fetcher = FakeInfo()                       # clearinghouseState: no position, no fills
    wire_master(fetcher)
    sender = fake_exchange({'status': 'ok', 'response': {'data': {'statuses': [
        {'filled': {'avgPx': '2500.0', 'totalSz': '0.008', 'oid': 9002}}]}}})
    svc.send_hyperliquid_order = sender
    iid = write_would_send('INV10-S2')
    svc.manual_send_one_intent(iid, True)
    rows = attempt_rows(iid)
    row = rows[-1] if rows else {}
    rec, terms, pos = snapshot()
    quote('S2 send_attempts row (ack only)', {k: row.get(k) for k in ('status', 'coin', 'side', 'copy_size')})
    quote('S2 settle status recorded', {'settle_status': rec.get('settle_status'), 'remaining': rec.get('remaining')})
    quote('S2 in_flight_terminals', terms)
    quote('S2 manual_live_positions', pos)
    check('S2 ack status is recorded verbatim as ORDER_FILLED (ack, not settlement)',
          row.get('status') == 'ORDER_FILLED', repr(row.get('status')))
    check('S2 MASTER flat => no settled ledger row', COIN not in terms, json.dumps(terms))
    check('S2 status recorded for the unresolvable ack is UNSETTLED',
          str(rec.get('settle_status')) == 'UNSETTLED', repr(rec.get('settle_status')))
    check('S2 MASTER flat => no position adopted from the ack', COIN not in pos, json.dumps(pos))
    check('S2 exactly one physical send attempted', len(sender.calls) == 1, str(len(sender.calls)))


# ---------------------------------------------------------------- S3
def case_s3():
    fresh_case()
    start = svc.utc_now_ms()
    fetcher = FakeInfo(positions={COIN: 0.008},
                       fills=[{'coin': COIN, 'side': 'B', 'sz': '0.008', 'px': '2500.0',
                               'oid': 9003, 'tid': 77, 'time': start, 'dir': 'Open Long'}])
    wire_master(fetcher)
    sender = fake_exchange({'status': 'ok', 'response': {'data': {'statuses': [
        {'filled': {'avgPx': '2500.0', 'totalSz': '0.008', 'oid': 9003}}]}}})
    svc.send_hyperliquid_order = sender
    iid = write_would_send('INV10-S3')
    svc.manual_send_one_intent(iid, True)
    rec, terms, pos = snapshot()
    quote('S3 in_flight_terminals', terms)
    quote('S3 manual_live_positions', pos)
    check('S3 MASTER fill+position => settlement granted', terms.get(COIN) == 'SETTLED_FULL', json.dumps(terms))
    check('S3 reservation cleared once settled', COIN not in (rec and {COIN: rec} or {}), json.dumps(rec))
    check('S3 position recorded only now that MASTER truth agrees',
          abs(float((pos.get(COIN) or {}).get('signed_size') or 0.0) - 0.008) < 1e-9, json.dumps(pos))
    check('S3 exactly one physical send attempted', len(sender.calls) == 1, str(len(sender.calls)))


# ---------------------------------------------------------------- S4
def case_s4():
    fresh_case()
    fetcher = FakeInfo(open_orders=[{'coin': COIN, 'oid': 9004, 'side': 'B', 'sz': '0.008',
                                     'limitPx': '2500.0'}])
    wire_master(fetcher)
    sender = fake_exchange(timeout=True)
    svc.send_hyperliquid_order = sender
    iid = write_would_send('INV10-S4')
    svc.manual_send_one_intent(iid, True)
    rows = attempt_rows(iid)
    row = rows[-1] if rows else {}
    rec, terms, pos = snapshot()
    for _ in range(3):                          # the loop/restart reconcile must never resend
        svc.reconcile_unresolved_send(COIN)
    rec2, terms2, pos2 = snapshot()
    quote('S4 send_attempts row (no ack)', {k: row.get(k) for k in ('status', 'coin', 'side', 'error')})
    quote('S4 MASTER openOrders (order is resting at the exchange)', fetcher.open_orders)
    quote('S4 reservation after 3 reconciles', rec2)
    check('S4 no ack => status ORDER_UNKNOWN, never filled', row.get('status') == 'ORDER_UNKNOWN', repr(row.get('status')))
    check('S4 no settled ledger row while MASTER shows no fill', COIN not in terms2, json.dumps(terms2))
    check('S4 reservation still blocking (fail closed)', COIN in (rec2 and {COIN: rec2} or {}), json.dumps(rec2))
    check('S4 recorded settle status is UNSETTLED', str(rec2.get('settle_status')) == 'UNSETTLED', repr(rec2.get('settle_status')))
    check('S4 no position recorded', COIN not in pos2, json.dumps(pos2))
    check('S4 settlement retries never cause a second physical send', len(sender.calls) == 1, str(len(sender.calls)))


# ---------------------------------------------------------------- S5
MUTATION_ANCHOR = '    size = abs(float(intent.get("size") or 0.0))\n'
MUTATION_BODY = (
    '    if str(intent.get("oid") or "").strip():\n'
    '        return {"settled": True, "status": SETTLE_FULL, "filled": float(intent.get("size") or 0.0),\n'
    '                "remaining": 0.0, "position_after": master_net}\n'
)


def case_s5():
    scratch = Path(tempfile.mkdtemp(prefix='inv10_s5_', dir=_SCRATCH)) / 'tree'
    scratch.mkdir(parents=True)
    for name in ('exchange_truth.py', 'HL_Live_Copy_Service.py',
                 'test_inv10_ack_is_not_settlement.py'):
        shutil.copy2(HERE / name, scratch / name)
    src = (scratch / 'exchange_truth.py').read_text(encoding='utf-8')
    if MUTATION_ANCHOR not in src:
        check('S5 mutation applied to the scratch copy', False, 'anchor not found in exchange_truth.py')
        return
    (scratch / 'exchange_truth.py').write_text(
        src.replace(MUTATION_ANCHOR, MUTATION_BODY + MUTATION_ANCHOR, 1), encoding='utf-8')
    print('RESULT::S5::scratch=' + str(scratch))
    print('RESULT::S5::mutation="an intent carrying an ack oid is treated as settled (SETTLED_FULL)"')
    env = {k: v for k, v in os.environ.items() if not k.startswith('PYTHON')}
    env['INV10_S5_CHILD'] = '1'
    env['HL_LIVE_ENV_FILE'] = '/nonexistent'
    proc = subprocess.run([sys.executable, '-u', str(scratch / 'test_inv10_ack_is_not_settlement.py')],
                          cwd=str(scratch), capture_output=True, text=True, env=env, timeout=300)
    out = (proc.stdout or '') + (proc.stderr or '')
    reddened = [ln.split('::')[2] for ln in out.splitlines() if ln.startswith('RESULT::FAIL::')]
    print('RESULT::S5::child_exit=' + str(proc.returncode))
    for name in reddened:
        print('RESULT::S5::reddened::' + name)
    if not reddened:
        print('RESULT::S5::child_tail=' + out[-600:].replace('\n', ' | '))
    check('S5 mutated tree goes RED (child exit 1)', proc.returncode == 1, 'rc=' + str(proc.returncode))
    check('S5 S1 reddens under the mutation', any(n.startswith('S1 ') for n in reddened), json.dumps(reddened))
    check('S5 S2 reddens under the mutation', any(n.startswith('S2 ') for n in reddened), json.dumps(reddened))


def main():
    print('RESULT::ENGINE_REV=' + subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=str(HERE),
                                                 capture_output=True, text=True).stdout.strip())
    print('RESULT::HARNESS_SHA256=' + __import__('hashlib').sha256(Path(__file__).read_bytes()).hexdigest())
    print('RESULT::OLFFLINE=no network: injected /info fetcher + injected exchange order double')
    for name, fn in (('S1', case_s1), ('S2', case_s2), ('S3', case_s3), ('S4', case_s4)):
        print('--- ' + name + ' ---')
        try:
            fn()
        except Exception as exc:  # a case that cannot run is a FAIL, never a silent skip
            check(name + ' case executed', False, repr(exc)[:300])
    if os.environ.get('INV10_S5_CHILD') != '1':
        print('--- S5 ---')
        try:
            case_s5()
        except Exception as exc:
            check('S5 case executed', False, repr(exc)[:300])
    print('RESULT::TOTAL=%d PASS=%d FAIL=%d' % (STATS['pass'] + STATS['fail'], STATS['pass'], STATS['fail']))
    print('RESULT::' + ('GREEN' if STATS['fail'] == 0 else 'RED'))
    return 0 if STATS['fail'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
