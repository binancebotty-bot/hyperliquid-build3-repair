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


class StubCfg:
    """Satisfies the master gate instead of being stopped by it.

    Why this exists: with a real ConfigManager over an empty temp audit dir, send_mode reads OFF, every order stops at
    the master gate (_master_gate_reason -> MASTER_REAL_ORDERS_OFF), no order reaches the fake exchange, and the file
    printed wire=None in all four cases - asserting nothing since the gate was added. Boss's standing rule needs a
    real wire value to compare against, so the gate is satisfied here and everything else answers safely.
    """

    config = {}

    def send_mode_now(self):
        return 'ON'

    def master_switch_now(self):
        return True

    def wallet_enabled(self, wallet):
        return True

    def wallet_mode(self, wallet):
        return 'LIVE'

    def marketable_bps(self):
        return 20.0

    def max_wallet_exposure(self, wallet):
        return 400.0

    def max_order_notional(self):
        return 250.0

    def max_total_exposure(self):
        return 900.0

    def max_asset_exposure(self):
        return 300.0

    def max_daily_loss(self):
        return 100.0

    def close_adverse_diff_pct(self):
        return 5.0

    def __getattr__(self, name):
        return lambda *a, **k: 0.0


class Led:
    def __init__(self, net):
        self.net = net
        self.data = {'by_wallet': {}, 'by_coin_net': {}}

    def coin_net(self, key):
        return self.net

    def wallet_abs_exposure_usd(self, wallet, prices=None):
        return 0.0


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
    gw = c.SenderGateway(StubCfg(), c.AuditLogWriter())
    gw._resolve_coin = lambda coin: dict(RESOLVED)
    gw._get_exchange_client = lambda *a, **k: fake
    gw._exchange_client_has_symbol = lambda *a, **k: True
    gw._validate_final_wire_order = lambda *a, **k: (True, {})
    gw._pre_exchange_asset_safety = lambda *a, **k: (True, {})
    gw._ensure_margin_mode = lambda *a, **k: None
    gw._withdraw_standing_close = lambda exchange, intent, wire_size, sz_dec, timing: (wire_size, None)
    gw._fresh_exchange_net = lambda coin: exchange_net
    gw.ledger = Led(ledger_net)
    intent = make_intent(side, size, lifecycle, name)
    ok, status, result = gw._send_real(intent)
    gw._append_real_attempt(intent, status, result)
    rows = [r for r in c.send_attempt_rows() if r.get('intent_id') == intent.intent_id]
    wire = fake.calls[0] if fake.calls else None
    audit = [str(r.get('reduce_only_sent')) for r in rows]
    check(name, bool(fake.calls) and all(a == str(wire) for a in audit),
          'wire=%s audit_rows=%s status=%s' % (wire, audit, status))
    if not fake.calls:
        check(name + '_REACHED_THE_EXCHANGE', False,
              'no order reached the fake exchange (status=%s): this case asserts nothing' % (status,))
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

failed = [n for n, ok in R if not ok]
print('TOTAL=%d FAILED=%d' % (len(R), len(failed)))
raise SystemExit(1 if failed else 0)
