#!/usr/bin/env python3
"""R4 v2: a PART-FILLED close must still send its remainder.

The rule under test: when an EXIT/REDUCE close comes back ORDER_FILLED with less than the wire size
(a thin book), the engine owes the rest. The remainder must reach the wire as a reduce-only standing
close, once, clamped to the copy-owned sleeve -- and must NOT reach the wire when the send switch is off.

Two independent defects are witnessed here, both on the remainder path:
  * the late wire gate (_final_close_proof) re-decides the close from timing["close_verified_sz_decimals"],
    and the ledger-lag wire plan never recorded that precision -- so the remainder was refused with
    CLOSE_PROOF_HOLD_UNKNOWN_PRECISION and exchange_called=False;
  * the remainder must stay bounded by the owned sleeve even when a same-side FOREIGN (user) residual
    inflates the exchange net.

Real ownership gate, real _close_wire_plan and the real physical-send path run. Only DATA sources are
faked: the exchange, the fresh exchange-net read, the persisted snapshot and the asset metadata.
Own temp state dir; offline; testnet.

Standalone process: python test_r4_part_filled_remainder.py
Prints RESULT::<NAME>_PASS|_FAIL per check and TOTAL=n FAILED=m; exits non-zero when anything failed.
"""
import csv
import os
import sys
import tempfile
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMP = Path(tempfile.mkdtemp(prefix='r4_part_filled_'))
os.environ.update({
    'HL_LIVE_AUDIT_DIR': str(TMP), 'HL_LIVE_ENV_FILE': str(TMP / 'missing.env'),
    'HL_LEADER_NETWORK': 'testnet', 'HL_FOLLOWER_NETWORK': 'testnet',
    'HL_LIVE_SCOPE_SWEEP_THREAD': '0', 'HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS': '0',
    'HL_LIVE_GLOBAL_LOCK_FILE': str(TMP / 'engine-global.lock'),
    'HL_LIVE_INTENT_DURABLE_WAIT_MS': '2000', 'PYTHONHASHSEED': '0',
})
for _k in ('HL_LIVE_HL_PRIVATE_KEY', 'HL_LIVE_HL_ACCOUNT_ADDRESS'):
    os.environ.pop(_k, None)
sys.path.insert(0, str(HERE))
import HL_Live_Copy_Service_Core as c  # noqa: E402

# the sender refuses unless the engine already owns the machine-wide lease: acquire it in the isolated temp path
c.acquire_global_instance_lock(TMP / 'state')

DUMMY_KEY = '0x' + '1' * 64            # synthetic, not a secret: only satisfies the credentials-present pre-check
A = '0x' + 'a' * 40                    # leader wallet A
ACCOUNT = '0x' + 'c' * 40              # the follower trading account (public address, not a secret)
COIN, PX, MIN_USD = 'BTC', 100.0, 10.0
RESOLVED = {'ok': True, 'sdk_coin': 'BTC', 'sz_decimals': 3, 'price_max_decimals': 2, 'perp_dexs': [''],
            'sdk_order_compatible': True, 'min_order_value_usd': MIN_USD, 'min_size': 0.0, 'status': 'OK'}

os.environ['HL_LIVE_HL_PRIVATE_KEY'] = DUMMY_KEY
os.environ['HL_LIVE_HL_ACCOUNT_ADDRESS'] = ACCOUNT
c.USER_WALLET = ACCOUNT
c.HLAccount, c.HLExchange = object, object
c.MIDS_FETCHER = lambda p: [] if isinstance(p, dict) and p.get('type') == 'perpDexs' else {'BTC': str(PX)}
c.LEADER_MIDS_FETCHER = c.MIDS_FETCHER

RESULTS = []


def check(name, ok, detail=''):
    ok = bool(ok)
    RESULTS.append((name, ok))
    print('RESULT::%s_%s%s' % (name, 'PASS' if ok else 'FAIL', ('' if ok or not detail else ' | ' + str(detail)[:700])),
          flush=True)


def case(name, fn):
    """Run one witness; an exception is a failed check carrying the exception text, never a crash."""
    try:
        ok, detail = fn()
    except Exception as exc:                                       # noqa: BLE001
        ok, detail = False, 'EXCEPTION %s: %s' % (type(exc).__name__, str(exc)[:300])
    check(name, ok, detail)


def filled(sz, px, oid=1):
    return {'status': 'ok', 'response': {'type': 'order', 'data': {'statuses': [
        {'filled': {'totalSz': str(sz), 'avgPx': str(px), 'oid': oid}}]}}}


def resting(oid):
    return {'status': 'ok', 'response': {'type': 'order', 'data': {'statuses': [{'resting': {'oid': oid}}]}}}


class FakeExchange:
    """Records every physical order call. Queued replies are consumed in order; with none left it fills
    exactly the size asked (a full fill). ``on_call`` runs after each call is recorded."""

    def __init__(self, replies=None, on_call=None):
        self.calls = []
        self.replies = list(replies or [])
        self.on_call = on_call
        self._lock = threading.Lock()

    def update_leverage(self, leverage, name, is_cross=True):
        return {'status': 'ok'}

    def order(self, coin, is_buy, size, px, tif, reduce_only=False, cloid=None):
        with self._lock:
            self.calls.append({'coin': coin, 'is_buy': is_buy, 'size': float(size), 'px': px,
                               'reduce_only': reduce_only, 'tif': tif, 'cloid': None if cloid is None else str(cloid)})
            reply = self.replies.pop(0) if self.replies else filled(size, px, oid=len(self.calls))
        if callable(self.on_call):
            self.on_call(self.calls[-1])
        return reply

    def cancel(self, coin, oid):
        return {'response': {'data': {'statuses': ['success']}}}


_n = [0]


def new_ledger():
    _n[0] += 1
    return c.ManualLedger(path=TMP / ('ledger_%d.json' % _n[0]))


def set_sleeve(ledger, wallet, signed):
    ledger.sleeve(wallet, COIN)['signed_size'] = signed
    ledger._recompute_net(ledger.data)


def clear_state():
    for p in (c.CLOSE_ESCALATIONS_FILE, c.STANDING_CLOSES_FILE):
        try:
            Path(p).unlink()
        except FileNotFoundError:
            pass


def make_gateway(ex, ledger, net, switch=None):
    gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), ledger)
    gw._resolve_coin = lambda coin: dict(RESOLVED)
    gw._get_exchange_client = lambda *a, **k: ex
    gw._exchange_client_has_symbol = lambda *a, **k: True
    gw._pre_exchange_asset_safety = lambda *a, **k: (True, {})
    gw._exchange_client_for_coin = lambda coin: (ex, 'BTC')
    gw._follower_order_account_for_proof = lambda *a, **k: ACCOUNT
    gw._fresh_exchange_net = lambda coin: net[0]
    gw._persisted_exchange_positions = lambda: (({'BTC': net[0]}, '') if net[0] is not None else ({}, 'unavailable'))
    gw.leader_reduced_since = lambda f: 0
    gw._margin_mode_done = {'BTC'}
    switch = switch if callable(switch) else (lambda: True)
    gw.cfg.master_switch_now = switch
    gw.cfg.send_mode_now = lambda: 'ON'
    gw.cfg.wallet_enabled = lambda w: True
    gw.cfg.wallet_mode = lambda w: 'ON'
    return gw


def exit_intent(ledger, wallet, side, size, fid, sleeve, source='POLL', ts=None):
    """A real, send-authorised EXIT intent built while the wallet sleeve holds ``sleeve`` (signed)."""
    set_sleeve(ledger, wallet, sleeve)
    fill = c.LeaderFill(fid, wallet, COIN, side, PX, size, ts if ts is not None else c.utc_now_ms(), source)
    it = c.IntentBuilder(c.ConfigManager(), ledger).build(fill)
    it.intent_id = fid
    it.decision = 'EXIT_ALLOWED'
    return it


def recon_rows(fid):
    p = c.RECONCILIATION_CSV
    if not p.exists():
        return []
    with p.open('r', newline='', encoding='utf-8-sig') as fh:
        return [r for r in csv.DictReader(fh) if r.get('leader_fill_id') == fid]


def escalation_rows():
    return c.load_json(c.CLOSE_ESCALATIONS_FILE, {}) or {}


def standing(sleeve_wallet=None):
    fn = getattr(c, 'load_json', None)
    return (fn(c.STANDING_CLOSES_FILE, {}) if fn else {}) or {}


def tif_is_gtc(tif):
    return str(tif).lower() == 'gtc' or (isinstance(tif, dict) and str(tif.get('limit', {}).get('tif', '')).lower() == 'gtc')


# =============================================================== PF1 the bug: part-filled remainder must send
def pf1():
    clear_state()
    led, ex, net = new_ledger(), FakeExchange(replies=[filled(0.5, PX, oid=1)]), [2.0]
    gw = make_gateway(ex, led, net)
    it = exit_intent(led, A, 'SELL', 2.0, 'pf1-f', 2.0)
    ok, status = gw.send_if_allowed(it)
    rows = recon_rows('pf1-f')
    rem = [x for x in ex.calls[1:]]
    return (ok and len(ex.calls) == 2 and abs(rem[0]['size'] - 1.5) < 1e-9 and rem[0]['reduce_only'] is True
            and tif_is_gtc(rem[0]['tif']) and rem[0]['is_buy'] is False
            and any(r.get('status') == 'EXIT_RECOVERY_QUEUED' for r in rows)
            and all(r.get('status') != 'EXIT_RECOVERY_QUEUE_FAILED' for r in rows)), \
        'ok=%r status=%r calls=%r rows=%r' % (ok, status, ex.calls, [(r.get('status'), r.get('terminal_state')) for r in rows])


# =============================================================== PF2 the remainder rests: it is tracked, not lost
def pf2():
    clear_state()
    led, ex, net = new_ledger(), FakeExchange(replies=[filled(0.5, PX, oid=1), resting(777)]), [2.0]
    gw = make_gateway(ex, led, net)
    it = exit_intent(led, A, 'SELL', 2.0, 'pf2-f', 2.0)
    ok, status = gw.send_if_allowed(it)
    stand = standing()
    rec = list(stand.values())[0] if stand else {}
    return (ok and len(ex.calls) == 2 and abs(rec.get('size', 0.0) - 1.5) < 1e-9 and rec.get('reduce_only') is True
            and str(rec.get('oid')) == '777'), \
        'ok=%r status=%r calls=%r standing=%r' % (ok, status, ex.calls, stand)


# =============================================================== PF3 switch OFF: nothing is sent at all
def pf3():
    clear_state()
    led, ex, net = new_ledger(), FakeExchange(), [2.0]
    gw = make_gateway(ex, led, net, switch=lambda: False)
    it = exit_intent(led, A, 'SELL', 2.0, 'pf3-f', 2.0)
    ok, status = gw.send_if_allowed(it)
    return (not ok and not ex.calls), 'ok=%r status=%r calls=%r' % (ok, status, ex.calls)


# =============================================================== PF4 switch OFF after the part-fill: no remainder
def pf4():
    clear_state()
    sw = {'off': False}
    ex = FakeExchange(replies=[filled(0.5, PX, oid=1)], on_call=lambda call: sw.update(off=True))
    led, net = new_ledger(), [2.0]
    gw = make_gateway(ex, led, net, switch=lambda: not sw['off'])
    it = exit_intent(led, A, 'SELL', 2.0, 'pf4-f', 2.0)
    ok, status = gw.send_if_allowed(it)
    esc = escalation_rows()
    return (len(ex.calls) == 1 and not standing()
            and any(v.get('state') == 'OPEN' for v in esc.values())), \
        'ok=%r status=%r calls=%r owed=%r' % (ok, status, ex.calls, esc)


# =============================================================== PF5 a full fill owes nothing
def pf5():
    clear_state()
    led, ex, net = new_ledger(), FakeExchange(replies=[filled(2.0, PX, oid=1)]), [2.0]
    gw = make_gateway(ex, led, net)
    it = exit_intent(led, A, 'SELL', 2.0, 'pf5-f', 2.0)
    ok, status = gw.send_if_allowed(it)
    return (ok and len(ex.calls) == 1 and not standing()), \
        'ok=%r status=%r calls=%r standing=%r' % (ok, status, ex.calls, standing())


# ============================== PF6 same-side FOREIGN (user) residual: the remainder is clamped to our sleeve
def pf6():
    clear_state()
    led, ex, net = new_ledger(), FakeExchange(replies=[filled(0.5, PX, oid=1)]), [5.0]   # engine +2, user +3 long
    gw = make_gateway(ex, led, net)
    it = exit_intent(led, A, 'SELL', 2.0, 'pf6-f', 2.0)
    ok, status = gw.send_if_allowed(it)
    rem = ex.calls[1:]
    return (ok and len(ex.calls) == 2 and abs(rem[0]['size'] - 1.5) < 1e-9 and rem[0]['reduce_only'] is True), \
        'ok=%r status=%r calls=%r' % (ok, status, ex.calls)


# ============================== PF7 the engine never closes a position it did not open
def pf7():
    clear_state()
    led, ex, net = new_ledger(), FakeExchange(), [5.0]              # the whole net is a user position
    gw = make_gateway(ex, led, net)
    it = exit_intent(led, A, 'SELL', 2.0, 'pf7-f', 2.0)             # built while the sleeve was owned ...
    (led.data.get('by_wallet') or {}).get(A, {}).pop(COIN, None)     # ... then the owner record is gone
    led._recompute_net(led.data)
    ok, status = gw.send_if_allowed(it)
    return (not ok and not ex.calls and status != 'ORDER_FILLED'), \
        'ok=%r status=%r calls=%r' % (ok, status, ex.calls)


# ============================== PF8 the precision is the exchange's, never a local default
def pf8():
    """No szDecimals in the metadata: the close must fail closed, not round on an invented precision."""
    clear_state()
    led, ex, net = new_ledger(), FakeExchange(replies=[filled(0.5, PX, oid=1)]), [2.0]
    gw = make_gateway(ex, led, net)
    gw._meta_cache = {'BTC': {'canonical_coin': 'BTC', 'sdk_coin': 'BTC', 'symbol_source': 'core_meta',
                              'perp_dex': '', 'tradable_by_sender': True}}   # NO szDecimals
    gw._meta_fetched = True
    gw._core_meta_fetched = True
    gw._asset_snapshot_loaded = True
    del gw._resolve_coin                    # the REAL resolver, not the fixture stub: the metadata is the witness
    res = gw._resolve_coin(COIN)
    it = exit_intent(led, A, 'SELL', 2.0, 'pf8-f', 2.0)
    ok, status = gw.send_if_allowed(it)
    return (not res.get('ok') and res.get('status') == 'SYMBOL_PRECISION_UNRESOLVED'
            and not ex.calls and not ok), \
        'res=%r ok=%r status=%r calls=%r' % (res, ok, status, ex.calls)


# ============================== PF9 szDecimals=0 is a real precision, not a missing one
def pf9():
    clear_state()
    led, ex, net = new_ledger(), FakeExchange(replies=[filled(0.5, PX, oid=1)]), [2.0]
    gw = make_gateway(ex, led, net)
    gw._meta_cache = {'BTC': {'canonical_coin': 'BTC', 'sdk_coin': 'BTC', 'symbol_source': 'core_meta',
                              'perp_dex': '', 'tradable_by_sender': True, 'szDecimals': 0}}
    gw._meta_fetched = True
    gw._core_meta_fetched = True
    gw._asset_snapshot_loaded = True
    del gw._resolve_coin
    res = gw._resolve_coin(COIN)
    it = exit_intent(led, A, 'SELL', 2.0, 'pf9-f', 2.0)
    ok, status = gw.send_if_allowed(it)
    rem = ex.calls[1:]
    return (res.get('ok') and res.get('sz_decimals') == 0 and ok and len(ex.calls) == 2
            and abs(rem[0]['size'] - 1.0) < 1e-9 and rem[0]['reduce_only'] is True), \
        'res=%r ok=%r status=%r calls=%r' % (res, ok, status, ex.calls)


def main():
    witnesses = [
        ('PF1_PART_FILLED_CLOSE_SENDS_ITS_REMAINDER_REDUCE_ONLY', pf1),
        ('PF2_RESTING_REMAINDER_IS_TRACKED_AS_THE_STANDING_CLOSE', pf2),
        ('PF3_SEND_SWITCH_OFF_SENDS_NOTHING', pf3),
        ('PF4_SWITCH_OFF_AFTER_THE_PART_FILL_SENDS_NO_REMAINDER_AND_OWES_IT', pf4),
        ('PF5_FULL_FILL_OWES_NO_REMAINDER', pf5),
        ('PF6_SAME_SIDE_FOREIGN_EXCESS_REMAINDER_IS_CLAMPED_TO_THE_COPY_OWNED_SLEEVE', pf6),
        ('PF7_ENGINE_NEVER_CLOSES_A_POSITION_IT_DID_NOT_OPEN', pf7),
        ('PF8_CLOSE_PRECISION_IS_EXCHANGE_PROVEN_NOT_A_LOCAL_DEFAULT', pf8),
        ('PF9_ZERO_SZ_DECIMALS_IS_HONOURED_NOT_TREATED_AS_MISSING', pf9),
    ]
    for nm, fn in witnesses:
        case(nm, fn)
    failed = [n for n, ok in RESULTS if not ok]
    print('TOTAL=%d FAILED=%d' % (len(RESULTS), len(failed)))
    if failed:
        print('FAILED: ' + ', '.join(failed))
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
