"""The send_attempts row must record the ACTUAL wire reduce_only flag, not a recomputed guess.

Every physical order goes through SenderGateway._place_order(reduce_only=...). The audit rows written for that
send (the pending_send row before the call and the final row after it) must carry that same value.

Failing-first (base 5b975f0): the pending_send row is written from intent.reduce_only_intended, while an EXIT
close trimmed to the follower's net target goes to the wire WITHOUT reduce-only (see _close_wire_plan).
The pending row then claims reduce_only_sent=True for an order that carried False.

Run (from _archive/hl_stage2): HL_LIVE_ENV_FILE=/nonexistent python -u test_core_audit_reduce_only_matches_wire.py
Offline: fake exchange, no network, no orders, no keys.
"""
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
R = []


def check(name, ok, detail=''):
    R.append((name, bool(ok)))
    print('RESULT::%s_%s%s' % (name, 'PASS' if ok else 'FAIL', (' | ' + detail) if (detail and not ok) else ''))


tmp = Path(tempfile.mkdtemp(prefix='audit_ro_'))
os.environ.update({
    'HL_LIVE_AUDIT_DIR': str(tmp), 'HL_LEADER_NETWORK': 'testnet', 'HL_FOLLOWER_NETWORK': 'testnet',
    'HL_LIVE_ENV_FILE': str(tmp / 'none.env'), 'HL_LIVE_HL_PRIVATE_KEY': '0x' + '1' * 64,
    'HL_LIVE_HL_ACCOUNT_ADDRESS': '0x' + 'c' * 40,
    'HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS': '0', 'HL_LIVE_CLOSE_TO_TARGET': '1',
})
import requests  # noqa: E402


def offline(*a, **k):
    raise RuntimeError('offline test: no network')


requests.post = offline
import HL_Live_Copy_Service_Core as c  # noqa: E402

c.requests.post = offline
c.USER_WALLET = '0x' + 'c' * 40
LEADER = '0x' + 'd' * 40


# module-level price helpers hit the network; pin both networks to the leader price
c.follower_mid = lambda coin: 100.0
c.leader_mid = lambda coin, use_cached=False: 100.0
c.follower_position_mark = lambda coin: 100.0


class FakeExchange:
    def __init__(self):
        self.calls = []

    def order(self, coin, is_buy, size, px, tif, reduce_only=False, cloid=None):
        self.calls.append(bool(reduce_only))
        return {'status': 'ok', 'response': {'type': 'order', 'data': {'statuses': [
            {'filled': {'totalSz': str(size), 'avgPx': str(px), 'oid': 1}}]}}}


RESOLVED = {'ok': True, 'sdk_coin': 'ZRO', 'sz_decimals': 2, 'price_max_decimals': 4, 'perp_dexs': [''],
            'sdk_order_compatible': True, 'min_order_value_usd': 1.0, 'min_size': 0.0, 'status': 'OK'}


class Led:
    def __init__(self, net, owned):
        self.net, self.owned = net, owned

    def coin_net(self, key):
        return self.net

    def sleeve(self, wallet, coin):
        return {"signed_size": self.owned}


def make_intent(side, size, lifecycle, tag):
    i = object.__new__(c.Intent)
    i.intent_id = 'i-%s-%s-%s-%s' % (tag, lifecycle, side, size)
    i.fill = c.LeaderFill('fid-' + i.intent_id, LEADER, 'ZRO', side, 100.0, 10.0, 1, 'TEST')
    i.copy_side = side
    i.copy_size = size
    i.copy_notional = abs(size * 100.0)
    i.copy_mode = 'fixed'
    i.wallet_mode = 'ON'
    i.decision = 'EXIT_ALLOWED'
    i.reason = lifecycle
    i.sleeve_id = 'sleeve-' + i.intent_id
    i.position_id = 'pos-' + i.intent_id
    i.position_direction_before = 'LONG'
    i.wallet_position_before = 0.0
    i.coin_net_before = 0.0
    i.reduce_only_intended = lifecycle in ('EXIT', 'REDUCE')
    i.reduce_only_sent_planned = False
    i.created_at_ms = 1
    i.notes = 'lifecycle=' + lifecycle
    return i


def run(name, side, size, ledger_net, exchange_net, lifecycle):
    fake = FakeExchange()
    # Each independent audit parity control has its own proven-fill history.
    c.CLOSE_RESERVATIONS_FILE = tmp / ('close_reservations_' + name + '.json')
    gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter())
    gw._resolve_coin = lambda coin: dict(RESOLVED)
    gw._get_exchange_client = lambda *a, **k: fake
    gw._exchange_client_has_symbol = lambda *a, **k: True
    gw._validate_final_wire_order = lambda *a, **k: (True, {})
    gw._pre_exchange_asset_safety = lambda *a, **k: (True, {})
    gw._ensure_margin_mode = lambda *a, **k: None
    gw._withdraw_standing_close = lambda exchange, intent, wire_size, sz_dec, timing: (wire_size, None)
    gw._fresh_exchange_net = lambda coin: exchange_net
    # Valid wire parity cases require a provable ENGINE sleeve, not just coin net.
    owned = (-size if side == 'BUY' else size) if lifecycle in ('EXIT', 'REDUCE') else 0.0
    gw.ledger = Led(ledger_net, owned)
    intent = make_intent(side, size, lifecycle, name)
    ok, status, result = gw._send_real(intent)
    gw._append_real_attempt(intent, status, result)
    rows = [r for r in c.send_attempt_rows() if r.get('intent_id') == intent.intent_id]
    wire = fake.calls[0] if fake.calls else None
    audit = [str(r.get('reduce_only_sent')) for r in rows]
    check(name, bool(fake.calls) and all(a == str(wire) for a in audit),
          'wire=%s audit_rows=%s status=%s' % (wire, audit, status))
    return wire


# Control 1: a reducing send (pure reduction inside the account net) is reduce-only on the wire and in the audit.
check('REDUCING_SEND_AUDIT_EQUALS_WIRE', run('REDUCING', 'BUY', 5.0, -10.0, -10.0, 'EXIT') is True)
# Control 2: an increasing send (entry) is not reduce-only on the wire and not in the audit.
check('INCREASING_SEND_AUDIT_EQUALS_WIRE', run('INCREASING', 'BUY', 2.0, 0.0, 0.0, 'ENTRY') is False)
# Control 3: pure_reduce boundary (opposing direction AND size == abs(net)) is reduce-only both places.
check('PURE_REDUCE_BOUNDARY_AUDIT_EQUALS_WIRE', run('BOUNDARY', 'BUY', 10.0, -10.0, -10.0, 'EXIT') is True)
# The defect: a close trimmed to the follower's net target is NOT a pure reduction, so the wire carries False
# even though the intent is an EXIT. The audit must say False too.
check('TRIMMED_CLOSE_AUDIT_EQUALS_WIRE', run('TRIMMED', 'BUY', 10.0, 0.0, 6.0, 'EXIT') is False)


# DIR131: no sleeve() cannot prove ENGINE ownership, so sender escalates RED
# without making an exchange call; it must NEVER crash or borrow USER net.
def test_missing_sleeve_returns_red_not_attribute_error():
    fake = FakeExchange()
    gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter())
    gw._resolve_coin = lambda coin: dict(RESOLVED)
    gw._get_exchange_client = lambda *a, **k: fake
    gw._exchange_client_has_symbol = lambda *a, **k: True
    gw._validate_final_wire_order = lambda *a, **k: (True, {})
    gw._pre_exchange_asset_safety = lambda *a, **k: (True, {})
    gw._ensure_margin_mode = lambda *a, **k: None
    gw._withdraw_standing_close = lambda exchange, intent, size, sz_dec, timing: (size, None)
    gw._fresh_exchange_net = lambda coin: -10.0
    class CoinNetOnly:
        def coin_net(self, key):
            return -10.0
    gw.ledger = CoinNetOnly()
    intent = make_intent('BUY', 5.0, 'EXIT', 'MISSING_SLEEVE')
    try:
        ok, status, result = gw._send_real(intent)
        check('UNPROVEN_ENGINE_SLEEVE_RED_NO_WIRE',
              not ok and not fake.calls and intent.sleeve_id in gw._trackb_escalations
              and result.get('exchange_called') is False
              and 'ENGINE_SLEEVE_UNPROVEN' in str(result.get('notes')),
              'ok=%r status=%r result=%r' % (ok, status, result))
    except Exception as exc:
        check('UNPROVEN_ENGINE_SLEEVE_RED_NO_WIRE', False, repr(exc))


test_missing_sleeve_returns_red_not_attribute_error()


# A flat read of follower A must not clear an owed close for SDK account B.
# Realistic fake-ledger sleeve() prevents a coin-net-only test double hiding this.
def test_fake_ledger_account_identity_cannot_clear():
    wallet_a, wallet_b = '0x' + 'a' * 40, '0x' + 'b' * 40
    saved_user = c.USER_WALLET
    saved_order = os.environ.get('HL_LIVE_HL_ACCOUNT_ADDRESS')
    saved_path = c.CLOSE_ESCALATIONS_FILE
    path = tmp / 'identity_close_escalations.json'
    row = {'leader_wallet': LEADER, 'coin': 'ZRO', 'intent_id': 'owed-i1',
           'leader_fill_id': 'owed-f1', 'state': 'OPEN'}
    calls = []
    try:
        c.USER_WALLET = wallet_a
        c.CLOSE_ESCALATIONS_FILE = path
        gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter())
        gw.ledger = Led(0.0, 0.0)
        gw._trackb_escalations = {'s1': row}
        c.atomic_write_json(path, dict(gw._trackb_escalations))
        exchange_net_by_account = {wallet_a: 0.0, wallet_b: 3.0}
        os.environ['HL_LIVE_HL_ACCOUNT_ADDRESS'] = wallet_b
        gw._fresh_exchange_net = lambda coin: (calls.append(coin) or exchange_net_by_account[wallet_a])
        cleared = gw.clear_trackb_escalations()
        check('FAKE_LEDGER_A_FLAT_B_NONFLAT_STAYS_RED',
              cleared == 0 and not calls and c.load_json(path, {}).get('s1') == row)
        # Account switched between initial identity check and the terminal write.
        os.environ['HL_LIVE_HL_ACCOUNT_ADDRESS'] = wallet_a
        calls.clear()
        def switch_account_after_read(coin):
            calls.append(coin)
            os.environ['HL_LIVE_HL_ACCOUNT_ADDRESS'] = wallet_b
            return exchange_net_by_account[wallet_a]
        gw._fresh_exchange_net = switch_account_after_read
        cleared = gw.clear_trackb_escalations()
        check('FAKE_LEDGER_ACCOUNT_CHANGED_DURING_READ_STAYS_RED',
              cleared == 0 and calls == ['ZRO'] and c.load_json(path, {}).get('s1') == row)
    except Exception as exc:
        check('FAKE_LEDGER_IDENTITY_REGRESSION', False, repr(exc))
    finally:
        c.USER_WALLET = saved_user
        c.CLOSE_ESCALATIONS_FILE = saved_path
        if saved_order is None:
            os.environ.pop('HL_LIVE_HL_ACCOUNT_ADDRESS', None)
        else:
            os.environ['HL_LIVE_HL_ACCOUNT_ADDRESS'] = saved_order


test_fake_ledger_account_identity_cannot_clear()

failed = [n for n, ok in R if not ok]
print('TOTAL=%d FAILED=%d' % (len(R), len(failed)))
raise SystemExit(1 if failed else 0)
