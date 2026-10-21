#!/usr/bin/env python3
"""READINESS 3 (GTC leg): the rate-limit recovery places a SECOND order. When the mid is worse than the
leader's price it rests a GTC limit on the book -- the path the IOC-retry suite never drives. That GTC
order must re-pass max_order_notional before the wire, and a GTC order inside the cap must still be sent.
Offline fakes only: no network, no keys, no synthetic orders.
Run: python test_gtc_repass_final_caps.py
"""
import csv
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
tmp = Path(tempfile.mkdtemp(prefix='gtc_repass_caps_'))
os.environ.update({'HL_LIVE_AUDIT_DIR': str(tmp), 'HL_LIVE_ENV_FILE': '/nonexistent'})
import HL_Live_Copy_Service_Core as c

R = []


def check(n, ok, d=''):
    R.append(bool(ok))
    print('RESULT::%s_%s%s' % (n, 'PASS' if ok else 'FAIL', (' | ' + str(d)) if d and not ok else ''))


RESOLVED = {'ok': True, 'sdk_coin': 'ZWIRE', 'sz_decimals': 2, 'price_max_decimals': 4,
            'perp_dexs': [''], 'sdk_order_compatible': True, 'min_order_value_usd': 1.0,
            'min_size': 0.0, 'status': 'OK'}


def cfg(max_order):
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {
        'auto_send_enabled': True,
        'wallets': {'0xw': {'enabled': True, 'mode': 'ON', 'copy_mode': 'fixed', 'fixed_notional': 100}},
        'global_controls': {'min_notional': 1, 'max_order_notional_usd': max_order, 'marketable_bps': 25},
    })


def intent(lifecycle='ENTRY', size=1.0, px=100.0):
    return c.Intent(
        intent_id='gtc-repass-1',
        fill=c.LeaderFill('lf-gtc-1', '0xw', 'ZWIRE', 'BUY', px, size, c.utc_now_ms(), 'TEST'),
        copy_side='BUY', copy_size=size, copy_notional=size * px,
        wallet_mode='ON', copy_mode='fixed', decision='ENTRY_ALLOWED', reason=lifecycle,
        sleeve_id='s1', position_id='p1', position_direction_before='FLAT',
        wallet_position_before=0.0, coin_net_before=0.0,
        reduce_only_intended=lifecycle in {'EXIT', 'REDUCE'}, reduce_only_sent_planned=False,
        notes='lifecycle=%s;' % lifecycle)


class FakeExchange:
    """Records every wire call; a resting reply is what a GTC limit that does not cross returns."""

    def __init__(self):
        self.calls = []

    def order(self, coin, is_buy, size, px, tif, reduce_only=False):
        self.calls.append({'px': px, 'size': size, 'tif': tif, 'reduce_only': reduce_only})
        return {'status': 'ok', 'response': {'data': {'statuses': [{'resting': {'oid': 'oid-%d' % len(self.calls)}}]}}}


def wired(max_order):
    cfg(max_order)
    g = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter())
    fe = FakeExchange()
    g._resolve_coin = lambda coin: dict(RESOLVED)
    g._get_exchange_client = lambda *a, **k: fe
    g._exchange_client_has_symbol = lambda *a, **k: True
    g._pre_exchange_asset_safety = lambda *a, **k: (True, {})
    g._validate_final_wire_order = lambda *a, **k: (True, {})
    g._ensure_margin_mode = lambda *a, **k: None
    g._begin_pending_send = lambda *a, **k: None
    g._symbol_reject_circuit_active = lambda resolved: False
    # mid ABOVE the leader's 100.0 buy price => the recovery takes the GTC leg, not the IOC retry
    g._fetch_all_mids = lambda: {'ZWIRE': 101.0}
    g._already_resting_block = lambda *a, **k: None
    return g, fe


def recovery(g, fe, size):
    return g._entry_add_rate_limit_recovery(
        fe, 'ZWIRE', intent('ENTRY'), 4, size, 100.0, size * 100.0, 'rate limited', {}, RESOLVED)


def recon_rows():
    path = c.RECONCILIATION_CSV
    if not Path(path).exists():
        return []
    with open(path, newline='', encoding='utf-8') as fh:
        return list(csv.DictReader(fh))


saved = (c.HLAccount, c.HLExchange, c.follower_mid, c.leader_mid, c.LEADER_NETWORK)
c.LEADER_NETWORK = c.FOLLOWER_NETWORK  # fixtures price on one network, as the engine's own tests do
c.HLAccount, c.HLExchange = object, object
c.follower_mid = lambda coin: 101.0
c.leader_mid = lambda coin, use_cached=True: 101.0
os.environ['HL_LIVE_HL_PRIVATE_KEY'] = '0x' + '1' * 64
try:
    # ---- GTC past the cap: blocked before the wire, reason on a terminal row ------------------------
    g1, fe1 = wired(100.5)
    blk = recovery(g1, fe1, 1.5)  # 1.5 @ 100.0 = 150.0 > 100.5
    check('GTC past max_order_notional blocked', blk is not None and blk[1] == 'RETRY_BLOCKED_FINAL_CAPS', blk)
    check('GTC past max_order_notional never reached the exchange',
          len(fe1.calls) == 0 and isinstance(blk, tuple) and blk[2].get('exchange_called') is False,
          (fe1.calls, blk))
    rows = [r for r in recon_rows()
            if r.get('intent_id') == 'gtc-repass-1' and r.get('terminal_state') == 'RETRY_BLOCKED_FINAL_CAPS']
    check('GTC block records a reason on the terminal row',
          len(rows) == 1 and 'blocked before the resend' in (rows[0].get('notes') or ''), rows)

    # ---- control: the same GTC path inside the cap is sent ------------------------------------------
    g2, fe2 = wired(100.5)
    ok2 = recovery(g2, fe2, 0.5)  # 0.5 @ 100.0 = 50.0 <= 100.5
    check('GTC control inside the cap is sent',
          len(fe2.calls) == 1 and fe2.calls[0]['tif'] == {'limit': {'tif': 'Gtc'}}, fe2.calls)
    check('GTC control inside the cap reports success',
          isinstance(ok2, tuple) and ok2[0] is True and ok2[2].get('exchange_called') is True, ok2)

    # ---- the guard itself, driven with the GTC leg's numbers ---------------------------------------
    guard = getattr(g2, '_repass_final_caps', None)
    check('HELPER exists', callable(guard))
    if callable(guard):
        check('HELPER GTC inside cap passes', guard(intent(), RESOLVED, 100.0, 0.5, 'ENTRY') is None)
        check('HELPER GTC past cap blocked',
              (guard(intent(), RESOLVED, 100.0, 1.5, 'ENTRY') or {}).get('status') == 'RETRY_BLOCKED_FINAL_CAPS')
finally:
    c.HLAccount, c.HLExchange, c.follower_mid, c.leader_mid, c.LEADER_NETWORK = saved
    os.environ.pop('HL_LIVE_HL_PRIVATE_KEY', None)

print('TOTAL=%d FAILED=%d' % (len(R), R.count(False)))
sys.exit(1 if False in R else 0)
