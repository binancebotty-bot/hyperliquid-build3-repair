#!/usr/bin/env python3
"""READINESS 3: a retry, reprice, min-size uplift and GTC fallback are SECOND exchange orders placed after the
final wire gate. Each must re-pass the final risk caps and may never grow past the size that gate approved.
Reductions always pass. Offline fakes only: no network, no keys, no synthetic orders.
Run: HL_LIVE_ENV_FILE=/nonexistent python test_core_repass_final_caps.py"""
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
tmp = Path(tempfile.mkdtemp(prefix='repass_caps_'))
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

def intent(lifecycle='ENTRY', size=1.0):
    return c.Intent(
        intent_id='repass-1',
        fill=c.LeaderFill('lf-1', '0xw', 'ZWIRE', 'BUY', 100.0, size, c.utc_now_ms(), 'TEST'),
        copy_side='BUY', copy_size=size, copy_notional=size * 100.0,
        wallet_mode='ON', copy_mode='fixed', decision='ENTRY_ALLOWED', reason=lifecycle,
        sleeve_id='s1', position_id='p1', position_direction_before='FLAT',
        wallet_position_before=0.0, coin_net_before=0.0,
        reduce_only_intended=lifecycle in {'EXIT', 'REDUCE'}, reduce_only_sent_planned=False,
        notes='lifecycle=%s;' % lifecycle)

def gw(max_order=100.5):
    cfg(max_order)
    g = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter())
    g._resolve_coin = lambda coin: dict(RESOLVED)
    return g

# ---- the guard itself ----------------------------------------------------------------------------------
g = gw()
guard = getattr(g, '_repass_final_caps', None)
check('HELPER exists', callable(guard))
if callable(guard):
    check('HELPER inside caps passes', guard(intent(), RESOLVED, 100.0, 1.0, 'ENTRY') is None)
    check('HELPER past max_order_notional blocked',
          (guard(intent(), RESOLVED, 101.0, 1.0, 'ENTRY') or {}).get('status') == 'RETRY_BLOCKED_FINAL_CAPS')
    for lc in ('EXIT', 'REDUCE'):
        check('HELPER %s reduction never blocked' % lc,
              guard(intent(lc), RESOLVED, 101.0, 5.0, lc) is None)

# ---- wire: IOC retry at a more aggressive price re-passes the caps --------------------------------------
class FakeExchange:
    def __init__(self):
        self.calls = []
    def order(self, coin, is_buy, size, px, tif, reduce_only=False):
        self.calls.append({'px': px, 'size': size, 'tif': tif})
        return {'status': 'ok', 'response': {'data': {'statuses': [{'error': 'Order could not immediately match'}]}}}

def wired(max_order):
    g = gw(max_order)
    fe = FakeExchange()
    g._get_exchange_client = lambda *a, **k: fe
    g._exchange_client_has_symbol = lambda *a, **k: True
    g._pre_exchange_asset_safety = lambda *a, **k: (True, {})
    g._validate_final_wire_order = lambda *a, **k: (True, {})
    g._ensure_margin_mode = lambda *a, **k: None
    g._begin_pending_send = lambda *a, **k: None
    g._symbol_reject_circuit_active = lambda resolved: False
    g._fetch_all_mids = lambda: {'ZWIRE': 100.0}
    g._already_resting_block = lambda *a, **k: None
    return g, fe

os.environ['HL_LIVE_MISSED_ENTRY_RULE'] = '0'  # so the IOC retry leg can price past the original limit
saved = (c.HLAccount, c.HLExchange, c.follower_mid, c.leader_mid, c.LEADER_NETWORK)
c.LEADER_NETWORK = c.FOLLOWER_NETWORK  # fixtures price on one network, as the engine's own tests do
c.HLAccount, c.HLExchange = object, object
c.follower_mid = lambda coin: 100.0
c.leader_mid = lambda coin, use_cached=True: 100.0
os.environ['HL_LIVE_HL_PRIVATE_KEY'] = '0x' + '1' * 64
try:
    g1, fe1 = wired(100.5)
    ok1, st1, _r1 = g1._send_real(intent('ENTRY'))
    check('WIRE retry past max_order_notional BLOCKED before the exchange',
          ok1 is False and st1 == 'RETRY_BLOCKED_FINAL_CAPS' and len(fe1.calls) == 1, (ok1, st1, fe1.calls))

    g2, fe2 = wired(0)
    _ok2, _st2, _r2 = g2._send_real(intent('ENTRY'))
    check('WIRE control uncapped retry reaches the exchange',
          len(fe2.calls) == 2 and fe2.calls[1]['px'] > fe2.calls[0]['px'], fe2.calls)
    check('WIRE control uncapped recovery reaches the exchange',
          len(fe2.calls) >= 1, fe2.calls)

    g3, fe3 = wired(100.5)
    blk = g3._entry_add_rate_limit_recovery(
        fe3, 'ZWIRE', intent('ENTRY'), 4, 1.01, 100.0, 101.0, 'rate limited', {}, RESOLVED)
    check('WIRE GTC recovery past max_order_notional blocked, reason recorded',
          blk is not None and blk[1] == 'RETRY_BLOCKED_FINAL_CAPS' and len(fe3.calls) == 0, (blk, fe3.calls))

    g4, fe4 = wired(0)
    g4._entry_add_rate_limit_recovery(
        fe4, 'ZWIRE', intent('ENTRY'), 4, 1.01, 100.0, 101.0, 'rate limited', {}, RESOLVED)
    check('WIRE control uncapped GTC recovery is sent', len(fe4.calls) == 1, fe4.calls)

    g5, fe5 = wired(100.5)
    ok5, st5, _r5 = g5._send_real(intent('REDUCE', size=5.0))
    check('WIRE REDUCE is never blocked by the caps', st5 != 'RETRY_BLOCKED_FINAL_CAPS', (ok5, st5))

    # min-size uplift: the symbol minimum would enlarge a near-min order past the cap. Refuse, never send bigger.
    c.follower_mid = lambda coin: 90.0
    c.leader_mid = lambda coin, use_cached=True: 90.0
    up = dict(RESOLVED); up['min_order_value_usd'] = 95.0
    g6, fe6 = wired(95.5)
    g6._resolve_coin = lambda coin: dict(up)
    ok6, st6, _r6 = g6._send_real(intent('ENTRY', size=1.0))
    check('WIRE min-size uplift past max_order_notional refused before the exchange',
          ok6 is False and st6 == 'SEND_NOT_ATTEMPTED_BELOW_SYMBOL_MIN_EXCEEDS_MAX_ORDER' and len(fe6.calls) == 0,
          (ok6, st6, fe6.calls))

    g7, fe7 = wired(0)
    g7._resolve_coin = lambda coin: dict(up)
    _ok7, _st7, _r7 = g7._send_real(intent('ENTRY', size=1.0))
    check('WIRE control uncapped min-size uplift is sent', len(fe7.calls) >= 1, fe7.calls)
    c.follower_mid = lambda coin: 100.0
    c.leader_mid = lambda coin, use_cached=True: 100.0
finally:
    c.HLAccount, c.HLExchange, c.follower_mid, c.leader_mid, c.LEADER_NETWORK = saved
    os.environ.pop('HL_LIVE_HL_PRIVATE_KEY', None)

print('TOTAL=%d FAILED=%d' % (len(R), R.count(False)))
sys.exit(1 if False in R else 0)
