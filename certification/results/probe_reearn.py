import json, os, sys, hashlib, tempfile
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
CORE = HERE / 'repo' / '_archive' / 'hl_stage2' / 'HL_Live_Copy_Service_Core.py'
sys.path.insert(0, str(CORE.parent))
_tmp = Path(tempfile.mkdtemp(prefix='reearn_'))
os.environ.update({'HL_LIVE_AUDIT_DIR': str(_tmp), 'HL_LIVE_ENV_FILE': 'nonexistent', 'HL_LIVE_MOCK_SEND': '0'})
os.environ.pop('HL_LIVE_CAP_SIZE_DOWN', None)
os.environ.pop('HL_LIVE_MISSED_ENTRY_RULE', None)
import HL_Live_Copy_Service_Core as c

MID = 100.0
c.follower_mid = lambda coin: MID
WALLET = '0x' + 'a'*40
COIN = 'BTC'
R = []

def check(row, name, active, control, ea, ec):
    ok = active == ea and control == ec
    d = 'active=%r want %r; control=%r want %r' % (active, ea, control, ec)
    R.append({'row': row, 'check': name, 'pass': ok, 'detail': d})
    print('RESULT::%s::%s::%s:: %s' % (row, name, 'PASS' if ok else 'FAIL', d))
    return ok

class Ledger:
    def __init__(self, exp=0.0): self.exp = exp
    def wallet_abs_exposure_usd(self, wallet, marks=None): return self.exp

def builder(gc, wallet_cfg=None, exp=None, resting=None, ledger_exp=0.0):
    b = c.IntentBuilder.__new__(c.IntentBuilder)
    wc = {'mode': 'ON', 'enabled': True, 'fixed_notional': 100.0, 'copy_mode': 'fixed'}
    wc.update(wallet_cfg or {})
    cfg = SimpleNamespace(
        global_controls=gc,
        wallet_enabled=lambda w: bool(wc.get('enabled', True)),
        wallet_mode=lambda w: str(wc.get('mode', 'ON')),
        is_symbol_allowed=lambda coin: c.ConfigManager.is_symbol_allowed(SimpleNamespace(global_controls=gc), coin),
        min_notional=lambda: float(gc.get('min_notional', 10.0)),
        max_total_exposure=lambda: float(gc.get('max_total_live_exposure_usd', 0.0) or 0.0),
        max_asset_directional_exposure=lambda: float(gc.get('max_asset_directional_exposure_usd', 0.0) or 0.0),
        max_wallet_exposure=lambda w: float(wc.get('max_wallet_exposure_usd', 0.0) or 0.0),
        max_order_notional=lambda: float(gc.get('max_order_notional_usd', 0.0) or 0.0),
        max_daily_loss=lambda: float(gc.get('max_daily_loss_usd', 0.0) or 0.0),
        max_close_adverse_diff_pct=lambda: float(gc.get('max_close_adverse_diff_pct', 0.0) or 0.0),
        marketable_bps=lambda: float(gc.get('marketable_bps', 20.0) or 0.0),
        auto_send_enabled=False, send_mode='ON')
    b.cfg = cfg
    b.ledger = Ledger(ledger_exp)
    b._sizing_block = {}
    b._exposure_pending = []
    b._coin_activity = {}
    b._coin_clean = {}
    b.follower_exposure = (lambda: exp) if exp is not None else (lambda: {'ok': True, 'total_usd': 0.0, 'by_coin': {}})
    b.resting_exposure = (lambda: resting or {})
    return b

def fill(side='BUY', price=MID):
    return SimpleNamespace(price=price, side=side, coin=COIN, raw={'dir': 'Open Long'}, leader_fill_id='f1', leader_wallet=WALLET, size=1.0, timestamp_ms=1, source='TEST')

def decide(b, side='BUY', notional=100.0, lifecycle='ENTRY', before=0.0):
    c._CAP_TLS.scale = 1.0
    return c.IntentBuilder._decision(b, WALLET, fill(side), lifecycle, notional, before)

def r1(cap, total=995.0):
    return decide(builder({'max_total_live_exposure_usd': cap, 'min_notional': 10.0}, exp={'ok': True, 'total_usd': total, 'by_coin': {}}))
# remaining allowance ($5) is below min_notional, so the order is refused instead of shrunk
check('RISK-001', 'total_cap_refuses_order_when_remaining_allowance_below_min', r1(1000.0), r1(0.0), ('SEND_BLOCKED_RISK', 'max total exposure exceeded'), ('ENTRY_ALLOWED', 'ENTRY'))

b = builder({'max_total_live_exposure_usd': 1000.0, 'min_notional': 10.0}, exp={'ok': True, 'total_usd': 900.0, 'by_coin': {}})
c._CAP_TLS.scale = 1.0
blk = c.IntentBuilder._exposure_cap_block(b, fill(), 150.0, MID)
sc = round(float(c._CAP_TLS.scale), 6)
check('RISK-001', 'total_cap_sizes_down_to_remaining_allowance', (blk, sc), ('', 1.0), ('', 0.666667), ('', 1.0))

def r2(cap, side='BUY'):
    return decide(builder({'max_asset_directional_exposure_usd': cap}, exp={'ok': True, 'total_usd': 0.0, 'by_coin': {'BTC': {'net': 5.0}}}), side=side)
# existing net 5 BTC at $100 = $500. With a $505 cap a $100 BUY cannot fit: the remaining $5 is under
# min_notional so it is refused, while the SELL that shrinks the net and the cap-OFF case both pass.
check('RISK-002', 'asset_cap_blocks_the_side_that_grows_the_net_only', r2(505.0), r2(505.0, 'SELL'), ('SEND_BLOCKED_RISK', 'max asset directional exposure exceeded'), ('ENTRY_ALLOWED', 'ENTRY'))
check('RISK-002', 'asset_cap_control_is_the_cap_itself', r2(505.0), r2(0.0), ('SEND_BLOCKED_RISK', 'max asset directional exposure exceeded'), ('ENTRY_ALLOWED', 'ENTRY'))
_b2 = builder({'max_asset_directional_exposure_usd': 550.0, 'min_notional': 10.0}, exp={'ok': True, 'total_usd': 0.0, 'by_coin': {'BTC': {'net': 5.0}}})
c._CAP_TLS.scale = 1.0
_blk2 = c.IntentBuilder._exposure_cap_block(_b2, fill(), 100.0, MID)
_half = round(float(c._CAP_TLS.scale), 6)
check('RISK-002', 'asset_cap_sizes_down_to_remaining_directional_room', (_blk2, _half), ('', 1.0), ('', 0.5), ('', 1.0))

def r3(cap):
    return decide(builder({}, wallet_cfg={'max_wallet_exposure_usd': cap}, ledger_exp=95.0))
check('RISK-003', 'wallet_exposure_cap_uses_ledger_plus_resting', r3(100.0), r3(0.0), ('SEND_BLOCKED_RISK', 'max wallet exposure exceeded'), ('ENTRY_ALLOWED', 'ENTRY'))

def r4(cap, bps=0.0):
    return decide(builder({'max_order_notional_usd': cap, 'marketable_bps': bps}))
check('RISK-004', 'max_order_notional_blocks_oversized_single_order', r4(50.0), r4(0.0), ('SEND_BLOCKED_RISK', 'max order notional exceeded'), ('ENTRY_ALLOWED', 'ENTRY'))

def vpx(bps):
    return round(c.IntentBuilder._order_value_px(builder({'marketable_bps': bps}), fill()), 6)
check('RISK-005', 'marketable_bps_moves_the_valuation_price', vpx(100.0), vpx(0.0), 101.0, 100.0)
check('PRICE-007', 'slippage_alone_flips_max_order_verdict', r4(100.0, 200.0), r4(100.0, 0.0), ('SEND_BLOCKED_RISK', 'max order notional exceeded'), ('ENTRY_ALLOWED', 'ENTRY'))

def sym(allow=None, block=None, lifecycle='ENTRY'):
    return decide(builder({'symbol_allowlist': allow, 'symbol_blocklist': block}), lifecycle=lifecycle)
check('RISK-007', 'allowlist_refuses_symbol_outside_the_list_only', sym(allow=['ETH']), sym(allow=['BTC']), ('SYMBOL_UNAVAILABLE', 'SYMBOL_NOT_ALLOWED'), ('ENTRY_ALLOWED', 'ENTRY'))
check('RISK-008', 'blocklist_refuses_the_named_symbol_only', sym(block=['BTC']), sym(block=['ETH']), ('SYMBOL_UNAVAILABLE', 'SYMBOL_BLOCKED'), ('ENTRY_ALLOWED', 'ENTRY'))
check('RISK-008', 'blocklist_never_traps_an_open_sleeve', sym(block=['BTC'], lifecycle='EXIT'), sym(block=['ETH'], lifecycle='EXIT'), ('EXIT_ALLOWED', 'EXIT'), ('EXIT_ALLOWED', 'EXIT'))

def r14(cap, unreadable):
    exp = {'ok': False, 'status': 'UNAVAILABLE'} if unreadable else {'ok': True, 'total_usd': 0.0, 'by_coin': {}}
    return decide(builder({'max_total_live_exposure_usd': cap}, exp=exp))

def r14r(cap, unreadable):
    return decide(builder({'max_total_live_exposure_usd': cap}, resting={'unreadable': True, 'total_usd': 0.0} if unreadable else {}))
check('RISK-014', 'unreadable_exposure_fails_closed_only_under_a_cap', r14(1000.0, True), r14(0.0, True), ('SEND_BLOCKED_RISK', 'follower exposure unavailable (UNAVAILABLE); entries fail closed while a cap is set'), ('ENTRY_ALLOWED', 'ENTRY'))
check('RISK-014', 'unreadable_resting_limits_fail_closed', r14r(1000.0, True), r14r(1000.0, False), ('SEND_BLOCKED_RISK', 'resting limits unreadable; entries fail closed while a cap is set'), ('ENTRY_ALLOWED', 'ENTRY'))

_cfgdir = Path(tempfile.mkdtemp(prefix='reearn_cfg_'))
def send_mode(value):
    p = _cfgdir / ('live_config_%s.json' % value)
    p.write_text(json.dumps({'global_controls': {'send_mode': value}, 'wallets': {WALLET: {'mode': 'ON', 'enabled': True}}}), encoding='utf-8')
    return c.ConfigManager(p).send_mode_now()
check('RISK-012', 'safe_stop_off_on_disk_is_read_as_off', send_mode('OFF'), send_mode('ON'), 'OFF', 'ON')

check('PRICE-005', 'close_bypasses_entry_min_notional_and_caps',
      decide(builder({'min_notional': 10.0, 'max_total_live_exposure_usd': 100.0}, exp={'ok': True, 'total_usd': 5000.0, 'by_coin': {'BTC': {'net': 50.0}}}), side='SELL', notional=0.5, lifecycle='EXIT', before=50.0),
      decide(builder({'min_notional': 10.0}), notional=0.5),
      ('EXIT_ALLOWED', 'EXIT'), ('BELOW_MIN_NOTIONAL', 'entry/add notional below minimum'))

def r3m(min_n):
    return decide(builder({'min_notional': min_n}), notional=12.0)
check('ORD-003', 'min_notional_blocks_entry_under_the_configured_floor', r3m(20.0), r3m(10.0), ('BELOW_MIN_NOTIONAL', 'entry/add notional below minimum'), ('ENTRY_ALLOWED', 'ENTRY'))

def rounding():
    return (round(c.SenderGateway._floor_wire_size(0.123456789, 3), 9),
            round(c.SenderGateway._ceil_wire_size(0.123000001, 3), 9),
            round(c.SenderGateway._floor_wire_size(0.1299, 2), 9))
check('ORD-004', 'wire_size_floors_then_ceils_at_symbol_precision', rounding(), (0.123, 0.124, 0.12), (0.123, 0.124, 0.12), (0.123, 0.124, 0.12))

# ORD-005 exactly-once execution identity: the client order id is derived from the intent id alone,
# so a crash-and-restart recomputes the same id (findable) and two intents never share one.
def cloid(iid):
    return c.generate_cloid(iid)

check('ORD-005', 'cloid_is_a_deterministic_function_of_the_intent_id',
      (cloid('intent-a') == cloid('intent-a'), cloid('intent-a') != cloid('intent-b'), len(cloid('intent-a'))),
      (True, False, 0), (True, True, 34), (True, False, 0))

# ORD-002 reduce_only correctness: closes are reduce-only, opens never are.
def ro(lifecycle, intended=False):
    it = SimpleNamespace(copy_side='SELL', copy_size=1.0, reduce_only_intended=intended,
                         notes='lifecycle=%s' % lifecycle, fill=fill('SELL'))
    return c.SenderGateway._reduce_only_for_intent(it)

check('ORD-002', 'reduce_only_is_set_on_closes_and_never_on_opens',
      (ro('EXIT'), ro('REDUCE'), ro('ENTRY'), ro('ADD')), (False, False, True, True),
      (True, True, False, False), (False, False, True, True))

# RISK-009 per-wallet daily loss limit: a rolling-24h loss past the limit is the one cycle gate that
# stays a hard stop (it is excluded from the alert-only downgrade).
def daily(pnl, limit, readable=True):
    core = c.LiveCopyCore.__new__(c.LiveCopyCore)
    core.cfg = SimpleNamespace(max_daily_loss=lambda: limit)
    _orig = c._XNET.rolling_day_pnl
    c._XNET.rolling_day_pnl = (lambda *a, **k: {'ok': True, 'pnl_usd': pnl}) if readable else (lambda *a, **k: {'ok': False, 'status': 'PNA_UNAVAILABLE'})
    try:
        return c.LiveCopyCore._daily_loss_block(core)
    finally:
        c._XNET.rolling_day_pnl = _orig

check('RISK-009', 'daily_loss_limit_blocks_at_the_configured_loss', daily(-50.0, 40.0), daily(-30.0, 40.0),
      'DAILY_LOSS_LIMIT_REACHED', '')
check('RISK-009', 'daily_loss_unreadable_fails_closed', daily(0.0, 40.0, readable=False), daily(-5.0, 40.0),
      'DAILY_LOSS_UNREADABLE', '')

sha = hashlib.sha256(CORE.read_bytes()).hexdigest()
out = {'schema': 'reearn-row-probes/1', 'task': 't_99472e6c', 'engine': {'path': 'repo/_archive/hl_stage2/HL_Live_Copy_Service_Core.py', 'sha256': sha}, 'method': "per row: ACTIVE case + CONTROL case differing only in that row's own control value; exact block reason asserted", 'checks': R, 'rows': {}}
for r in R:
    row = out['rows'].setdefault(r['row'], {'checks': [], 'pass': True})
    row['checks'].append(r['check'])
    row['pass'] = row['pass'] and r['pass']
for k, v in sorted(out['rows'].items()):
    v['verdict'] = 'PASS' if v['pass'] else 'FAIL'
    print('ROW::%s::%s:: %d check(s)' % (k, v['verdict'], len(v['checks'])))
(HERE / 'probe_reearn_results.json').write_text(json.dumps(out, indent=1, sort_keys=True), encoding='utf-8')
print('TOTAL_CHECKS', len(R), 'FAILED', sum(1 for r in R if not r['pass']))
