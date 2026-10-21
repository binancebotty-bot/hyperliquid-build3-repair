#!/usr/bin/env python3
"""ENG-INV-10: an exchange ack is not settlement; the MASTER copy account must show it.

Offline only: fake exchange client + injected MASTER truth fetcher (MASTER_TRUTH_FETCHER).
No keys, no orders, no network, no engine start.

Run: python test_core_settlement_verification.py   # RESULT:: markers, exit 0/1.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

MASTER = '0x' + 'a' * 40
SIGNER = '0x' + 'b' * 40
RESULTS = []


def check(name, cond, detail=''):
    RESULTS.append((name, bool(cond)))
    print('RESULT::%s_%s%s' % (name, 'PASS' if cond else 'FAIL', (' | ' + str(detail)) if (detail and not cond) else ''))


class MasterTruth:
    """Offline /info double for the MASTER reads: perpDexs, userFillsByTime, openOrders."""

    def __init__(self, fill_sz=None, resting_oid=None, down=False, fill_oid=42):
        self.fill_sz, self.resting_oid, self.down = fill_sz, resting_oid, down
        self.fill_oid = fill_oid
        self.calls = []

    def __call__(self, payload):
        self.calls.append(payload.get('type'))
        if self.down:
            raise RuntimeError('MASTER scope unavailable')
        kind = payload.get('type')
        if kind == 'perpDexs':
            return []
        if kind == 'userFillsByTime':
            if self.fill_sz is None:
                return []
            return [{'coin': 'BTC', 'side': 'B', 'sz': str(self.fill_sz), 'px': '100',
                     'oid': self.fill_oid, 'tid': 1, 'time': 1}]
        if kind == 'openOrders':
            return [{'coin': 'BTC', 'oid': self.resting_oid}] if self.resting_oid is not None else []
        raise RuntimeError('unexpected payload %r' % (payload,))


class FakeExchange:
    def __init__(self, ack_size, oid=42, reject_first=False):
        self.calls, self.ack_size, self.oid, self.reject_first = [], ack_size, oid, reject_first

    def order(self, coin, is_buy, size, px, tif, reduce_only=False):
        self.calls.append({'coin': coin, 'size': size, 'px': px, 'reduce_only': reduce_only})
        if self.reject_first and len(self.calls) == 1:
            return {'status': 'ok', 'response': {'type': 'order', 'data': {'statuses': [
                {'error': 'Order could not immediately match'}]}}}
        if self.ack_size is None:
            return {'status': 'ok', 'response': {'type': 'order', 'data': {'statuses': [
                {'resting': {'oid': self.oid}}]}}}
        body = {'totalSz': str(self.ack_size), 'avgPx': str(px)}
        if self.oid is not None:
            body['oid'] = self.oid
        return {'status': 'ok', 'response': {'type': 'order', 'data': {'statuses': [{'filled': body}]}}}


def setup(truth, exchange):
    tmp = Path(tempfile.mkdtemp(prefix='coreinv10_'))
    os.environ.update({
        'HL_LIVE_AUDIT_DIR': str(tmp),
        'HL_LIVE_ENV_FILE': str(tmp / 'none.env'),
        'HL_LEADER_NETWORK': 'mainnet',
        'HL_FOLLOWER_NETWORK': 'testnet',
        'HL_LIVE_HL_ACCOUNT_ADDRESS': MASTER,
        'HL_LIVE_HL_SIGNER_ADDRESS': SIGNER,
        'HL_LIVE_HL_PRIVATE_KEY': '0x' + '1' * 64,
    })
    import HL_Live_Copy_Service_Core as c
    c.MASTER_TRUTH_FETCHER = truth
    c.MIDS_FETCHER = lambda p: [] if p.get('type') == 'perpDexs' else {'BTC': '100'}
    c._FOLLOWER_MIDS.update(px={}, ms=0)
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {'auto_send_enabled': False, 'global_controls': {}, 'wallets': {
        MASTER: {'enabled': True, 'mode': 'ON', 'copy_mode': 'fixed', 'fixed_notional': 100}}})
    resolved = {'ok': True, 'sdk_coin': 'BTC', 'sz_decimals': 3, 'price_max_decimals': 2, 'perp_dexs': [''],
                'sdk_order_compatible': True, 'min_order_value_usd': 1.0, 'min_size': 0.0, 'status': 'OK'}
    intent = c.IntentBuilder(c.ConfigManager(), c.ManualLedger(path=tmp / 'ledger.json')).build(
        c.LeaderFill('f1', MASTER, 'BTC', 'BUY', 100.0, 1.0, c.utc_now_ms(), 'TEST'))
    gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter())
    gw._resolve_coin = lambda coin: dict(resolved)
    gw._get_exchange_client = lambda *a, **k: exchange
    gw._exchange_client_has_symbol = lambda *a, **k: True
    gw._validate_final_wire_order = lambda *a, **k: (True, {})
    gw._pre_exchange_asset_safety = lambda *a, **k: (True, {})
    saved = c.HLAccount, c.HLExchange
    c.HLAccount, c.HLExchange = object, object
    return c, gw, intent, saved


def send(truth, exchange):
    c, gw, intent, saved = setup(truth, exchange)
    try:
        ok, status, res = gw._send_real(intent)
    finally:
        c.HLAccount, c.HLExchange = saved
    return ok, status, res, intent, gw


def ledger_claims(c, intent_id):
    """True if live_fills.csv holds any row for this intent."""
    path = Path(c.LIVE_FILLS_CSV)
    if not path.exists():
        return False
    return any(str(r.get('intent_id') or '') == str(intent_id) for r in c.read_csv_rows(path))


def main():
    wire = 1.0  # fixed_notional 100 at follower mid 100 -> 1.0 BTC

    ok, status, res, _i, _g = send(MasterTruth(fill_sz=0.4), FakeExchange(ack_size=wire))
    check('S1_MASTER_SMALLER_FILL_DOES_NOT_SETTLE', ok is False and status == 'SETTLEMENT_UNVERIFIED',
          '%s %s' % (status, res.get('notes')))
    check('S1_ROW_HOLDS_FOR_RECONCILIATION',
          res.get('terminal_state') == 'SETTLEMENT_UNVERIFIED'
          and res.get('operator_action') == 'WAIT_FOR_RECONCILIATION'
          and res.get('write_reconciliation') is True, json.dumps(res, default=str)[:300])
    check('S1_ACK_IS_NOT_BOOKED_AS_SETTLED', not str(status).startswith('ORDER_FILLED'), status)

    ok, status, res, _i, _g = send(MasterTruth(fill_sz=wire), FakeExchange(ack_size=wire))
    check('S2_MASTER_AGREES_SETTLES_AS_BEFORE', ok is True and status == 'ORDER_FILLED', '%s %s' % (ok, status))

    ok, status, res, _i, _g = send(MasterTruth(down=True), FakeExchange(ack_size=wire))
    check('S3_MASTER_UNAVAILABLE_FAILS_CLOSED', ok is False and status == 'SETTLEMENT_UNVERIFIED',
          '%s %s' % (status, res.get('notes')))

    ok, status, res, _i, _g = send(MasterTruth(resting_oid=7), FakeExchange(ack_size=None, oid=7))
    check('S4_RESTING_PROVED_BY_MASTER_OPEN_ORDERS', ok is True and status == 'ORDER_RESTING',
          '%s %s' % (ok, res.get('notes')))

    ok, status, res, _i, _g = send(MasterTruth(resting_oid=8), FakeExchange(ack_size=None, oid=7))
    check('S5_RESTING_ABSENT_ON_MASTER_DOES_NOT_SETTLE', ok is False and status == 'SETTLEMENT_UNVERIFIED',
          '%s %s' % (status, res.get('notes')))

    # An ACK with no oid, plus a MASTER fill of exactly the ACK size, same coin and side,
    # belonging to someone else. Nothing correlates it to our order, so it must not be booked.
    c6, gw6, intent6, saved6 = setup(MasterTruth(fill_sz=wire), FakeExchange(ack_size=wire, oid=None))
    try:
        ok, status, res = gw6._send_real(intent6)
    finally:
        c6.HLAccount, c6.HLExchange = saved6
    check('S6_NO_OID_SAME_SIZE_FILL_IS_NOT_OURS', ok is False and status == 'SETTLEMENT_UNVERIFIED',
          '%s %s' % (status, res.get('notes')))
    check('S6_ROW_SAYS_UNVERIFIED',
          res.get('terminal_state') == 'SETTLEMENT_UNVERIFIED'
          and res.get('operator_action') == 'WAIT_FOR_RECONCILIATION'
          and res.get('write_reconciliation') is True,
          json.dumps(res, default=str)[:300])
    check('S6_ALERT_FIRES_RED',
          c6.classify_integrity_severity('SETTLEMENT_UNVERIFIED') == 'RED',
          c6.classify_integrity_severity('SETTLEMENT_UNVERIFIED'))
    check('S6_LEDGER_CLAIMS_NO_FILL', not ledger_claims(c6, intent6.intent_id), intent6.intent_id)

    # Control: identical sizes, but the ACK carries the oid that the MASTER fill carries.
    ok, status, res, _i, _g = send(MasterTruth(fill_sz=wire, fill_oid=42), FakeExchange(ack_size=wire, oid=42))
    check('S6C_SAME_SIZES_WITH_MATCHING_OID_SETTLES', ok is True and status == 'ORDER_FILLED',
          '%s %s' % (status, res.get('notes')))

    ok, status, res, _i, _g = send(MasterTruth(fill_sz=0.4), FakeExchange(ack_size=wire, reject_first=True))
    check('S7_ENTRY_IOC_RETRY_FILL_ALSO_VERIFIED', ok is False and status == 'SETTLEMENT_UNVERIFIED',
          '%s %s' % (status, res.get('notes')))

    # Revert control (see 02_red_log.txt): with the removed coin+side+size branch restored,
    # S6 above books the stranger's fill and goes RED. That run is captured, not simulated here.
    c, gw, intent, saved = setup(MasterTruth(fill_sz=0.4), FakeExchange(ack_size=wire))
    original = c.SenderGateway._verify_settlement_on_master
    c.SenderGateway._verify_settlement_on_master = lambda *a, **k: (True, '')
    try:
        ok, status, _res = gw._send_real(intent)
    finally:
        c.SenderGateway._verify_settlement_on_master = original
        c.HLAccount, c.HLExchange = saved
    check('S8_REVERT_CONTROL_WITHOUT_VERIFICATION_BOOKS_THE_ACK', ok is True and status == 'ORDER_FILLED',
          'reverted engine returned %s %s' % (ok, status))

    failed = [n for n, good in RESULTS if not good]
    print('TOTAL=%d FAILED=%d' % (len(RESULTS), len(failed)))
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
