#!/usr/bin/env python3
"""C7 close-must-send witnesses (tests FIRST; written before the Core predicate exists).

Source of the witnesses: Reviewer's C4a plan, PR #8 on binancebotty-bot/hermes-gpt-control, comments 6506577678 and
6506663891 (W1..W9), plus the commit-4 failure shapes (B_REAL_SEND, restart with a stale/consumed exit intent).

The rule under test: an EXIT/REDUCE intent is refused with the named no-send
SEND_NOT_ATTEMPTED_STALE_OR_CONSUMED_FLAT_SLEEVE ONLY when its exact wallet+coin engine sleeve is PROVEN flat/absent AND
(the fill is PROVEN stale replay OR was already terminally consumed). Everything else keeps the existing close behaviour:
a close of an open sleeve is never refused by this gate (netting closes that raise gross exposure, a user residual on the
coin, whole-position dust, ...).

What is REAL: SenderGateway.send_if_allowed, _send_real, the ownership gate (_pre_send_ownership_gate), the final-wire
validator (_validate_final_wire_order), _close_wire_plan, the audit writers and the escalation store.
What is STUBBED (make_gateway): the asset metadata (_resolve_coin), the SDK client (_get_exchange_client,
_exchange_client_for_coin, _exchange_client_has_symbol -> the fake exchange), the pre-exchange asset safety check
(_pre_exchange_asset_safety), leader_reduced_since, the margin-mode cache, the master/wallet switch reads (cfg.* -> ON), the
persisted exchange snapshot (_persisted_exchange_positions) and, EXCEPT in W6B/W6C, the fresh exchange-net read
(_fresh_exchange_net -> a number the test controls). W6B/W6C use the REAL _fresh_exchange_net and fake only the HTTP
fetcher (c.EXPOSURE_FETCHER), answering per account address. Own temp state dir; offline; testnet.

Standalone process: python test_core_c7_close_must_send.py
Prints RESULT::<NAME>_PASS|_FAIL per check and TOTAL=n FAILED=m; exits non-zero when anything failed.
"""
import csv
import os
import sys
import tempfile
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMP = Path(tempfile.mkdtemp(prefix="c7_must_send_"))
os.environ.update({
    "HL_LIVE_AUDIT_DIR": str(TMP), "HL_LIVE_ENV_FILE": str(TMP / "missing.env"),
    "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
    "HL_LIVE_SCOPE_SWEEP_THREAD": "0", "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0",
    "HL_LIVE_GLOBAL_LOCK_FILE": str(TMP / "engine-global.lock"),
    "HL_LIVE_INTENT_DURABLE_WAIT_MS": "2000", "PYTHONHASHSEED": "0",
})
for _k in ("HL_LIVE_HL_PRIVATE_KEY", "HL_LIVE_HL_ACCOUNT_ADDRESS"):
    os.environ.pop(_k, None)
sys.path.insert(0, str(HERE))
import HL_Live_Copy_Service_Core as c  # noqa: E402

NAME = "SEND_NOT_ATTEMPTED_STALE_OR_CONSUMED_FLAT_SLEEVE"
DUMMY_KEY = "0x" + "1" * 64            # synthetic, not a secret: only satisfies the credentials-present pre-check
A = "0x" + "a" * 40                    # leader wallet A
B = "0x" + "b" * 40                    # leader wallet B
ACCOUNT = "0x" + "c" * 40              # the follower trading account (public address, not a secret)
OTHER_ACCOUNT = "0x" + "d" * 40
COIN, PX, MIN_USD = "BTC", 100.0, 10.0
RESOLVED = {"ok": True, "sdk_coin": "BTC", "sz_decimals": 3, "price_max_decimals": 2, "perp_dexs": [""],
            "sdk_order_compatible": True, "min_order_value_usd": MIN_USD, "min_size": 0.0, "status": "OK"}

os.environ["HL_LIVE_HL_PRIVATE_KEY"] = DUMMY_KEY
os.environ["HL_LIVE_HL_ACCOUNT_ADDRESS"] = ACCOUNT
c.USER_WALLET = ACCOUNT
c.HLAccount, c.HLExchange = object, object
c.MIDS_FETCHER = lambda p: [] if isinstance(p, dict) and p.get("type") == "perpDexs" else {"BTC": str(PX)}
c.LEADER_MIDS_FETCHER = c.MIDS_FETCHER

RESULTS = []


def check(name, ok, detail=""):
    ok = bool(ok)
    RESULTS.append((name, ok))
    print("RESULT::%s_%s%s" % (name, "PASS" if ok else "FAIL", ("" if ok or not detail else " | " + str(detail)[:600])), flush=True)


def case(name, fn):
    """Run one witness; an exception is a failed check carrying the exception text, never a crash."""
    try:
        ok, detail = fn()
    except Exception as exc:                                       # noqa: BLE001
        ok, detail = False, "EXCEPTION %s: %s" % (type(exc).__name__, str(exc)[:300])
    check(name, ok, detail)


def filled(sz, px, oid=1):
    return {"status": "ok", "response": {"type": "order", "data": {"statuses": [
        {"filled": {"totalSz": str(sz), "avgPx": str(px), "oid": oid}}]}}}


class FakeExchange:
    """Records every physical order call. With no queued replies it fills exactly the size asked (a full fill)."""

    def __init__(self, replies=None, on_order=None):
        self.calls = []
        self.replies = list(replies or [])
        self.on_order = on_order
        self._lock = threading.Lock()

    def update_leverage(self, leverage, name, is_cross=True):
        return {"status": "ok"}

    def order(self, coin, is_buy, size, px, tif, reduce_only=False, cloid=None):
        with self._lock:
            self.calls.append({"coin": coin, "is_buy": is_buy, "size": float(size), "px": px, "reduce_only": reduce_only,
                               "cloid": None if cloid is None else str(cloid)})
            if self.on_order is not None:
                self.on_order(self.calls[-1])
            if self.replies:
                return self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
            return filled(size, px, oid=len(self.calls))

    def cancel(self, coin, oid):
        return {"response": {"data": {"statuses": ["success"]}}}


_n = [0]


def new_ledger():
    _n[0] += 1
    return c.ManualLedger(path=TMP / ("ledger_%d.json" % _n[0]))


def set_sleeve(ledger, wallet, signed):
    ledger.sleeve(wallet, COIN)["signed_size"] = signed
    ledger._recompute_net(ledger.data)


def durable(ledger, wallet):
    """Persist the ledger (explicitly touching this wallet's sleeve) and reload it from disk: durable state, not memory."""
    ledger.save(touched_sleeves=[(wallet, COIN)])
    return c.ManualLedger(path=ledger.path)


def account_fetcher(positions):
    """An HTTP fetcher for c.EXPOSURE_FETCHER answering per account address (lower-case keys -> signed BTC size)."""
    def fetch(p):
        if p.get("type") == "perpDexs":
            return []
        n = positions.get(str(p.get("user", "")).lower())
        ap = [] if not n else [{"position": {"coin": "BTC", "szi": str(n), "positionValue": str(abs(n) * PX)}}]
        return {"assetPositions": ap, "marginSummary": {"accountValue": "1000"}}
    return fetch


def make_gateway(ex, ledger, net, account=ACCOUNT, snapshot=True, real_fresh=False):
    """A real SenderGateway; the REAL _pre_send_ownership_gate, _validate_final_wire_order, _close_wire_plan and
    send path run. Only data sources are replaced."""
    gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), ledger)
    gw._resolve_coin = lambda coin: dict(RESOLVED)
    gw._get_exchange_client = lambda *a, **k: ex
    gw._exchange_client_has_symbol = lambda *a, **k: True
    gw._pre_exchange_asset_safety = lambda *a, **k: (True, {})
    gw._exchange_client_for_coin = lambda coin: (ex, "BTC")
    gw._follower_order_account_for_proof = lambda *a, **k: account
    if not real_fresh:
        gw._fresh_exchange_net = lambda coin: net[0]
    if snapshot:
        gw._persisted_exchange_positions = lambda: (({"BTC": net[0]}, "") if net[0] is not None else ({}, "unavailable"))
    gw.leader_reduced_since = lambda f: 0
    gw._margin_mode_done = {"BTC"}
    gw.cfg.master_switch_now = lambda: True
    gw.cfg.send_mode_now = lambda: "ON"
    gw.cfg.wallet_enabled = lambda w: True
    gw.cfg.wallet_mode = lambda w: "ON"
    return gw


def exit_intent(ledger, wallet, side, size, fid, sleeve, source="POLL", ts=None):
    """A real, send-authorised EXIT intent built while the wallet sleeve holds ``sleeve`` (signed)."""
    set_sleeve(ledger, wallet, sleeve)
    fill = c.LeaderFill(fid, wallet, COIN, side, PX, size, ts if ts is not None else c.utc_now_ms(), source)
    it = c.IntentBuilder(c.ConfigManager(), ledger).build(fill)
    it.intent_id = fid
    it.decision = "EXIT_ALLOWED"
    return it


def recon_rows(fid):
    p = c.RECONCILIATION_CSV
    if not p.exists():
        return []
    with p.open("r", newline="", encoding="utf-8-sig") as fh:
        return [r for r in csv.DictReader(fh) if r.get("leader_fill_id") == fid]


def named_rows(fid):
    return [r for r in recon_rows(fid) if NAME in (r.get("terminal_state"), r.get("status"))]


def named_btw(it):
    return named_rows(it.fill.leader_fill_id)


def sleeve_of(ledger, wallet):
    row = ((ledger.data.get("by_wallet") or {}).get(wallet) or {}).get(COIN)
    return None if row is None else float(row.get("signed_size"))


# ======================================================================================= W1 stale replay, flat sleeve
def w1():
    led, ex, net = new_ledger(), FakeExchange(), [0.0]
    gw = make_gateway(ex, led, net)
    it = exit_intent(led, A, "SELL", 2.0, "w1-f", 2.0, source="WS_SNAPSHOT_REPLAY", ts=1)
    set_sleeve(led, A, 0.0)                                          # the position is gone: explicit 0, persisted and reloaded
    led = durable(led, A)
    gw = make_gateway(ex, led, net)
    assert sleeve_of(led, A) == 0.0, "durable flat sleeve not loaded from disk"
    ok, status = gw.send_if_allowed(it)
    rows = recon_rows("w1-f")
    return (not ok and status == NAME and not ex.calls and len(rows) == 1 and len(named_rows("w1-f")) == 1
            and str(rows[0].get("engine_can_send")) in ("False", "false", "0", "")), \
        "ok=%r status=%r calls=%d rows=%r" % (ok, status, len(ex.calls), [(r.get("status"), r.get("terminal_state")) for r in rows])


# ======================================================================================= W2 netted opposite-leader reduction
def w2():
    led, net = new_ledger(), [-5.0]
    on_order, sold = _fills_hook(net, led)
    ex = FakeExchange(on_order=on_order)
    gw = make_gateway(ex, led, net)
    set_sleeve(led, B, -15.0)                                        # leader B short 15: exchange net = +10 - 15 = -5
    it = exit_intent(led, A, "SELL", 10.0, "w2-f", 10.0)
    ok, status = gw.send_if_allowed(it)
    return ok and len(ex.calls) == 1 and abs(ex.calls[0]["size"] - 10.0) < 1e-9 and ex.calls[0]["reduce_only"] is False \
        and abs(net[0] - (-15.0)) < 1e-9, \
        "ok=%r status=%r calls=%r exchange_net_after=%r (expected -15, gross rises 5 -> 15, non-reduce-only)" % (ok, status, ex.calls, net[0])


def w2b():
    led, net = new_ledger(), [5.0]
    on_order, sold = _fills_hook(net, led)
    ex = FakeExchange(on_order=on_order)
    gw = make_gateway(ex, led, net)
    set_sleeve(led, B, -5.0)                                         # leader B short 5: exchange net = +10 - 5 = +5
    it = exit_intent(led, A, "SELL", 10.0, "w2b-f", 10.0)
    ok, status = gw.send_if_allowed(it)
    return ok and len(ex.calls) == 1 and abs(ex.calls[0]["size"] - 10.0) < 1e-9 and ex.calls[0]["reduce_only"] is False \
        and abs(net[0] - (-5.0)) < 1e-9, \
        "ok=%r status=%r calls=%r exchange_net_after=%r (expected -5, non-reduce-only)" % (ok, status, ex.calls, net[0])


# ======================================================================================= W3 live sleeve / user residual
def w3a():
    led, ex, net = new_ledger(), FakeExchange(), [2.0]
    gw = make_gateway(ex, led, net)
    it = exit_intent(led, A, "SELL", 1.0, "w3a-f", 2.0)
    ok, status = gw.send_if_allowed(it)
    return ok and len(ex.calls) == 1 and ex.calls[0]["reduce_only"] is True and abs(ex.calls[0]["size"] - it.copy_size) < 1e-9, \
        "ok=%r status=%r calls=%r copy_size=%r" % (ok, status, ex.calls, it.copy_size)


def w3b_user_residual():
    led, ex, net = new_ledger(), FakeExchange(), [5.5]   # engine +0.5, a user-managed +5 on the same coin
    gw = make_gateway(ex, led, net)
    it = exit_intent(led, A, "SELL", 0.5, "w3b-f", 0.5)
    ok, status = gw.send_if_allowed(it)
    return ok and len(ex.calls) == 1 and abs(ex.calls[0]["size"] - it.copy_size) < 1e-9 and ex.calls[0]["reduce_only"] is True, \
        "ok=%r status=%r calls=%r" % (ok, status, ex.calls)


# ======================================================================================= W4 dust
def w4a_whole_position():
    led, ex, net = new_ledger(), FakeExchange(), [0.05]
    gw = make_gateway(ex, led, net)
    it = exit_intent(led, A, "SELL", 0.05, "w4a-f", 0.05)
    ok, status = gw.send_if_allowed(it)
    return ok and len(ex.calls) == 1 and abs(ex.calls[0]["size"] - 0.05) < 1e-9 and ex.calls[0]["reduce_only"] is True, \
        "ok=%r status=%r calls=%r" % (ok, status, ex.calls)


def w4b_submin_remainder_is_held_not_sent():
    led, ex, net = new_ledger(), FakeExchange(), [5.05]               # engine +0.05 ($5) with a user +5 residual
    gw = make_gateway(ex, led, net)
    it = exit_intent(led, A, "SELL", 0.05, "w4b-f", 0.05)
    ok, status = gw.send_if_allowed(it)
    sub_min = [x for x in ex.calls if x["size"] * PX < MIN_USD - 1e-9]
    esc = c.load_json(c.CLOSE_ESCALATIONS_FILE, {}) or {}
    open_red = [k for k, v in esc.items() if A.lower() in k.lower() and v.get("state") == "OPEN"]
    terminal = [r for r in recon_rows("w4b-f") if (r.get("terminal_state") in c.TERMINAL_ROW_NAMES or r.get("status") in c.TERMINAL_ROW_NAMES)]
    return (not ok) and not sub_min and bool(open_red) and not terminal, \
        "ok=%r status=%r calls=%r open_red=%r terminal_rows=%r" % (ok, status, ex.calls, open_red, [(r.get("status"), r.get("terminal_state")) for r in terminal])


def w4c_resolved_by_whole_position_close_when_account_would_go_flat():
    led, ex, net = new_ledger(), FakeExchange(), [5.05]
    gw = make_gateway(ex, led, net)
    it = exit_intent(led, A, "SELL", 0.05, "w4c-f", 0.05)
    ok1, st1 = gw.send_if_allowed(it)                                        # held: sub-minimum with a residual
    net[0] = 0.05                                                            # the user residual is gone: the engine's 0.05 is the whole position
    before = len(ex.calls)
    ok, status = gw.send_if_allowed(it)                                      # the SAME fill id retried through the same path
    new = ex.calls[before:]
    return (not ok1) and ok and len(new) == 1 and abs(new[0]["size"] - 0.05) < 1e-9 and new[0]["reduce_only"] is True, \
        "first=%r/%r retry=%r/%r new_calls=%r" % (ok1, st1, ok, status, new)


def w4d_no_engine_dust_remains_when_exchange_is_flat():
    """Isolated: its own wallet and its own escalation store (the Core's CLOSE_ESCALATIONS_FILE is redirected for this
    witness), so 'no open red' is judged on this witness alone."""
    D0 = "0x" + "e" * 40
    saved = c.CLOSE_ESCALATIONS_FILE
    c.CLOSE_ESCALATIONS_FILE = TMP / "w4d_close_escalations.json"
    try:
        led, ex, net = new_ledger(), FakeExchange(), [5.05]
        gw = make_gateway(ex, led, net)
        gw.send_if_allowed(exit_intent(led, D0, "SELL", 0.05, "w4d-f1", 0.05))   # held
        net[0] = 0.0                                                            # the asset is flat on the exchange
        before = len(ex.calls)
        gw.send_if_allowed(exit_intent(led, D0, "SELL", 0.05, "w4d-f2", 0.05))
        for nm in ("clear_close_escalations", "clear_trackb_escalations"):      # the periodic double-flat clear, either name
            fn = getattr(gw, nm, None)
            if callable(fn):
                fn()
        esc = c.load_json(c.CLOSE_ESCALATIONS_FILE, {}) or {}
        sl = sleeve_of(led, D0)
        open_red = [k for k, v in esc.items() if v.get("state") == "OPEN"]
    finally:
        c.CLOSE_ESCALATIONS_FILE = saved
    return sl is not None and abs(sl) < 1e-9 and not open_red and len(ex.calls) == before, \
        "sleeve=%r open_red=%r new_calls=%d" % (sl, open_red, len(ex.calls) - before)


# ======================================================================================= B_REAL_SEND shape
def b_real_send():
    led, ex, net = new_ledger(), FakeExchange(), [0.05]
    gw = make_gateway(ex, led, net)
    it = exit_intent(led, A, "SELL", 0.05, "breal-f", 0.05)
    ok, status, res = gw._send_real(it)
    return ok and len(ex.calls) == 1 and ex.calls[0]["reduce_only"] is True and (res or {}).get("exchange_called", True) is not False, \
        "ok=%r status=%r calls=%r exchange_called=%r" % (ok, status, ex.calls, (res or {}).get("exchange_called"))


def b_real_send_public_path():
    led, ex, net = new_ledger(), FakeExchange(), [0.05]
    gw = make_gateway(ex, led, net)
    it = exit_intent(led, A, "SELL", 0.05, "breal-pub-f", 0.05)
    ok, status = gw.send_if_allowed(it)
    rows = [r for r in c.send_attempt_rows() if r.get("intent_id") == it.intent_id]
    return ok and len(ex.calls) == 1 and ex.calls[0]["reduce_only"] is True and bool(rows), \
        "ok=%r status=%r calls=%r send_attempt_rows=%d" % (ok, status, ex.calls, len(rows))


# ======================================================================================= W5 older terminal id
def w5():
    led, ex, net = new_ledger(), FakeExchange(), [2.0]
    gw = make_gateway(ex, led, net)
    gw.audit.append_reconciliation("SEND_TERMINAL", "ORDER_FILLED", leader_wallet=A, leader_fill_id="w5-old", intent_id="w5-old",
                                   coin=COIN, terminal_state="ORDER_FILLED", engine_can_send="False")
    it = exit_intent(led, A, "SELL", 1.0, "w5-new", 2.0)
    ok, status = gw.send_if_allowed(it)
    return ok and len(ex.calls) == 1 and not named_rows("w5-new"), "ok=%r status=%r calls=%r" % (ok, status, ex.calls)


# ======================================================================================= W6 unknown / wrong account never claims flat
def w6a_unreadable_exchange_never_claims_flat():
    led, ex, net = new_ledger(), FakeExchange(), [None]
    gw = make_gateway(ex, led, net)
    it = exit_intent(led, A, "SELL", 2.0, "w6a-f", 2.0)
    ok, status = gw.send_if_allowed(it)
    sl = sleeve_of(led, A)
    named_hold = str(status).startswith("OWNERSHIP_GATE_") or "HOLD" in str(status)
    return status != NAME and not named_btw(it) and (not ex.calls) and named_hold and sl is not None and abs(sl - 2.0) < 1e-9, \
        "ok=%r status=%r sdk_calls=%d named_hold=%r sleeve=%r" % (ok, status, len(ex.calls), named_hold, sl)


def w6b_wrong_account_flat_read_never_claims_flat_and_close_is_sent():
    """REAL vulnerability: c.USER_WALLET (the account _fresh_exchange_net READS) is not the account the orders go to
    (HL_LIVE_HL_ACCOUNT_ADDRESS / the SDK signer). The real _fresh_exchange_net reads the reader account, whose answer
    is flat; the engine's own account still holds +2. A flat read of the wrong account must not zero the sleeve or
    drop the close. (Only the HTTP fetcher is faked, answering per address.)"""
    led, ex = new_ledger(), FakeExchange()
    gw = make_gateway(ex, led, [None], real_fresh=True)
    gw._persisted_exchange_positions = lambda: ({"BTC": 2.0}, "")            # the engine's own account snapshot: still +2
    saved_w, saved_f = c.USER_WALLET, c.EXPOSURE_FETCHER
    c.USER_WALLET = OTHER_ACCOUNT                                             # the reader account != the trading account
    c.EXPOSURE_FETCHER = account_fetcher({ACCOUNT.lower(): 2.0, OTHER_ACCOUNT.lower(): 0.0})
    try:
        it = exit_intent(led, A, "SELL", 2.0, "w6b-f", 2.0)
        ok, status = gw.send_if_allowed(it)
        read = gw._fresh_exchange_net(COIN)
    finally:
        c.USER_WALLET, c.EXPOSURE_FETCHER = saved_w, saved_f
    sl = sleeve_of(led, A)
    return read == 0.0 and status != NAME and sl is not None and abs(sl - 2.0) < 1e-9 and ok and len(ex.calls) == 1, \
        "fresh_read=%r (the other account: flat) ok=%r status=%r sleeve=%r calls=%r" % (read, ok, status, sl, ex.calls)


def w6c_wrong_account_exchange_reject_never_zeroes_the_sleeve():
    """Same real wrong-account read (the reader account reads flat; the trading account holds +2). The unknown read means
    the close is SENT from the sleeve, reduce-only; the injected exchange reject occurs and is handled; the flat-repair
    branch is actually REACHED (spied, the real function still runs) and must not zero the sleeve; the close stays owed."""
    reject = {"status": "ok", "response": {"type": "order", "data": {"statuses": [
        {"error": "Reduce only order would increase position."}]}}}
    led, ex = new_ledger(), FakeExchange([reject])
    gw = make_gateway(ex, led, [None], real_fresh=True)
    gw._persisted_exchange_positions = lambda: ({"BTC": 2.0}, "")
    repair_calls = []
    real_repair = gw._repair_ledger_if_exchange_flat

    def spy(intent, exchange_error):
        repair_calls.append(str(exchange_error))
        return real_repair(intent, exchange_error)
    gw._repair_ledger_if_exchange_flat = spy
    saved_w, saved_f = c.USER_WALLET, c.EXPOSURE_FETCHER
    c.USER_WALLET = OTHER_ACCOUNT
    c.EXPOSURE_FETCHER = account_fetcher({ACCOUNT.lower(): 2.0, OTHER_ACCOUNT.lower(): 0.0})
    try:
        it = exit_intent(led, A, "SELL", 2.0, "w6c-f", 2.0)
        ok, status = gw.send_if_allowed(it)
    finally:
        c.USER_WALLET, c.EXPOSURE_FETCHER = saved_w, saved_f
    sl = sleeve_of(led, A)
    esc = c.load_json(c.CLOSE_ESCALATIONS_FILE, {}) or {}
    owed = [k for k, v in esc.items() if A.lower() in k.lower() and v.get("state") == "OPEN"]
    first_reduce_only = bool(ex.calls) and ex.calls[0]["reduce_only"] is True
    reject_handled = (not ok) and status != "SEND_NOT_ATTEMPTED_CLOSE_AT_TARGET"
    return (first_reduce_only and len(ex.calls) >= 1 and reject_handled and bool(repair_calls)
            and sl is not None and abs(sl - 2.0) < 1e-9 and bool(owed)), \
        ("first_call_reduce_only=%r sdk_calls=%d ok=%r status=%r repair_branch_reached=%d (%r) sleeve=%r owed_open_red=%r"
         % (first_reduce_only, len(ex.calls), ok, status, len(repair_calls), repair_calls[:1], sl, owed))


# ======================================================================================= W7 held / ambiguous is not consumed
def w7_held_same_fill_is_not_consumed():
    led, ex, net = new_ledger(), FakeExchange(), [0.0]
    gw = make_gateway(ex, led, net)
    it = exit_intent(led, A, "SELL", 0.05, "w7-f", 0.05)                      # live source, fresh timestamp: not stale
    set_sleeve(led, A, 0.0)
    gw.audit.append_reconciliation("CLOSE_HELD", "HELD_CLOSE_REMAINDER", leader_wallet=A, leader_fill_id="w7-f", intent_id="w7-f",
                                   coin=COIN, action="RETRY_HELD_ENGINE_CLOSE", engine_can_close="True")
    ok, status = gw.send_if_allowed(it)
    return status != NAME and not named_rows("w7-f"), "ok=%r status=%r" % (ok, status)


# ======================================================================================= W8 absent key, partial ledger
def w8_absent_key_in_a_partial_ledger_is_unknown():
    led, ex, net = new_ledger(), FakeExchange(), [0.0]
    gw = make_gateway(ex, led, net)
    it = exit_intent(led, A, "SELL", 1.0, "w8-f", 1.0, source="WS_SNAPSHOT_REPLAY", ts=1)
    data = {k: v for k, v in led.data.items()}
    data["by_wallet"] = {w: v for w, v in (led.data.get("by_wallet") or {}).items() if w != A}   # the wallet is missing on disk
    c.atomic_write_json(led.path, data)
    led = c.ManualLedger(path=led.path)
    gw = make_gateway(ex, led, net)
    ok, status = gw.send_if_allowed(it)
    fabricated = ((led.data.get("by_wallet") or {}).get(A) or {}).get(COIN)
    return status != NAME and not named_rows("w8-f") and fabricated is None, \
        "ok=%r status=%r fabricated=%r" % (ok, status, fabricated)


# ======================================================================================= W9 two simultaneous stale replays
def w9():
    led, ex, net = new_ledger(), FakeExchange(), [0.0]
    gw = make_gateway(ex, led, net)
    it = exit_intent(led, A, "SELL", 2.0, "w9-f", 2.0, source="WS_SNAPSHOT_REPLAY", ts=1)
    set_sleeve(led, A, 0.0)
    led = durable(led, A)
    gw = make_gateway(ex, led, net)
    assert sleeve_of(led, A) == 0.0, "durable flat sleeve not loaded from disk"
    gate, out = threading.Barrier(2), []

    def go():
        gate.wait()
        out.append(gw.send_if_allowed(it))

    ts = [threading.Thread(target=go) for _ in range(2)]
    [t.start() for t in ts]
    [t.join(30) for t in ts]
    return len(named_rows("w9-f")) == 1 and not ex.calls, \
        "named_rows=%d calls=%d results=%r" % (len(named_rows("w9-f")), len(ex.calls), out)


# ======================================================================================= W3C / W3D oversize and user residual
def _fills_hook(net, led):
    sold = []

    def on_order(call):
        sz = call["size"] * (1 if call["is_buy"] else -1)
        net[0] += sz
        set_sleeve(led, A, sleeve_of(led, A) + sz)
        sold.append(call["size"])
    return on_order, sold


def w3c_oversize_close_never_sent_at_the_users_size():
    led, net = new_ledger(), [5.5]                                           # engine +0.5, user-managed +5
    on_order, sold = _fills_hook(net, led)
    ex = FakeExchange(on_order=on_order)
    gw = make_gateway(ex, led, net)
    it = exit_intent(led, A, "SELL", 0.9, "w3c-f", 0.5)
    it.copy_size = 0.9                                                       # an oversize close: larger than the engine sleeve
    ok, status = gw.send_if_allowed(it)
    return all(x["size"] <= 0.5 + 1e-9 for x in ex.calls) and net[0] >= 5.0 - 1e-9, \
        "ok=%r status=%r calls=%r exchange_net_after=%r (cut to the sleeve or refused; never the user's size)" % (
            ok, status, ex.calls, net[0])


def w3d_user_residual_untouched_after_the_engine_close():
    led, net = new_ledger(), [5.5]
    on_order, sold = _fills_hook(net, led)
    ex = FakeExchange(on_order=on_order)
    gw = make_gateway(ex, led, net)
    it = exit_intent(led, A, "SELL", 0.5, "w3d-f", 0.5)
    ok, status = gw.send_if_allowed(it)
    sl = sleeve_of(led, A)
    return ok and abs(net[0] - 5.0) < 1e-9 and sl is not None and abs(sl) < 1e-9 and abs(sum(sold) - 0.5) < 1e-9, \
        "ok=%r status=%r exchange_net_after=%r (user residual must stay 5.0) sleeve=%r sold=%r" % (ok, status, net[0], sl, sold)


# ======================================================================================= W-A STOP RACE (negative control)
def w_a_stop_race():
    """Last read mode was LIVE; the operator then wrote OFF (a new generation); the send-time mode read raises; a genuine
    pending owned close exists. Required: ZERO SDK sends and a durable RED obligation that survives a restart."""
    led, ex, net = new_ledger(), FakeExchange(), [2.0]
    gw = make_gateway(ex, led, net)
    it = exit_intent(led, A, "SELL", 2.0, "wa-f", 2.0)

    def unreadable():
        raise RuntimeError("mode file unreadable (operator generation changed)")
    gw.cfg.send_mode_now = unreadable
    try:
        res = gw.send_if_allowed(it)
    except Exception as exc:                                                 # noqa: BLE001
        res = ("EXCEPTION", "%s: %s" % (type(exc).__name__, str(exc)[:80]))
    esc = c.load_json(c.CLOSE_ESCALATIONS_FILE, {}) if hasattr(c, "CLOSE_ESCALATIONS_FILE") else {}
    open_now = [k for k, v in (esc or {}).items() if v.get("state") == "OPEN"]
    gw2 = make_gateway(ex, led, net)                                         # simulated restart
    restarted = getattr(gw2, "_close_escalations", None) or {}
    open_after = [k for k, v in restarted.items() if v.get("state") == "OPEN"]
    return not ex.calls and bool(open_now) and bool(open_after), \
        "result=%r sdk_calls=%d open_red_on_disk=%r open_red_after_restart=%r" % (res, len(ex.calls), open_now, open_after)


# ======================================================================================= W-B SAME NET, DIFFERENT OWNERSHIP (CLO)
def _wb(owned):
    led, net = new_ledger(), [10.0]                                          # master coin +10 in both variants
    on_order, sold = _fills_hook(net, led)
    ex = FakeExchange(on_order=on_order)
    gw = make_gateway(ex, led, net)
    gw.cfg.wallet_mode = lambda w: "CLO"                                     # CLOSE ONLY: reductions allowed, entries not
    it = exit_intent(led, A, "SELL", 3.0, "wb-%s-f" % ("own" if owned else "foreign"), 10.0)
    it.copy_size = 3.0                                                       # the event-derived owed reduction
    if not owned:
        set_sleeve(led, A, 0.0)                                              # the +10 is somebody else's
    ok, status = gw.send_if_allowed(it)
    return ex, net, led, ok, status, sold


def w_b_owned():
    ex, net, led, ok, status, sold = _wb(True)
    return ok and len(ex.calls) == 1 and abs(ex.calls[0]["size"] - 3.0) < 1e-9 and ex.calls[0]["reduce_only"] is True and ex.calls[0]["is_buy"] is False, \
        "ok=%r status=%r calls=%r" % (ok, status, ex.calls)


def w_b_foreign():
    ex, net, led, ok, status, sold = _wb(False)
    sl = sleeve_of(led, A)
    print("W_B_FOREIGN_STATUS=%r" % (status,))
    return (not ok) and not ex.calls and abs(net[0] - 10.0) < 1e-9 and (sl is None or abs(sl) < 1e-9) and bool(status), \
        "ok=%r status=%r calls=%r exchange_net=%r sleeve=%r" % (ok, status, ex.calls, net[0], sl)


# ======================================================================================= restart: consumed exit vs flat everything
def restart_consumed_exit_never_opens_a_position():
    led, ex, net = new_ledger(), FakeExchange(), [2.0]
    gw1 = make_gateway(ex, led, net)
    it = exit_intent(led, A, "SELL", 2.0, "rs-f", 2.0)
    ok1, st1 = gw1.send_if_allowed(it)                                        # the close goes out and fills
    set_sleeve(led, A, 0.0)
    net[0] = 0.0                                                              # sleeve flat AND exchange flat
    led = durable(led, A)                                                     # persisted, then reloaded by the restart
    gw2 = make_gateway(ex, led, net)                                          # the restart
    before = len(ex.calls)
    ok2, st2 = gw2.send_if_allowed(it)                                        # the same stale exit intent is replayed
    new = ex.calls[before:]
    return ok1 and not new, "first=%r/%r replay=%r/%r new_calls=%r" % (ok1, st1, ok2, st2, new)


def main():
    witnesses = [
        ("W1_STALE_REPLAY_ON_FLAT_SLEEVE_IS_A_NAMED_NO_SEND_WITH_ONE_DURABLE_ROW", w1),
        ("W2_NETTED_OPPOSITE_LEADER_REDUCTION_STILL_SENDS_GROSS_RISES", w2),
        ("W2B_NETTED_OPPOSITE_LEADER_REDUCTION_STILL_SENDS", w2b),
        ("W3A_LIVE_SLEEVE_CLOSE_SENDS_REDUCE_ONLY", w3a),
        ("W3B_USER_RESIDUAL_ON_THE_COIN_ENGINE_CLOSE_OF_ITS_OWN_SLEEVE_STILL_SENDS", w3b_user_residual),
        ("W3C_OVERSIZE_CLOSE_IS_CUT_TO_THE_ENGINE_SLEEVE_OR_REFUSED_NEVER_SENT_AT_THE_USERS_SIZE", w3c_oversize_close_never_sent_at_the_users_size),
        ("W3D_USER_RESIDUAL_IS_UNTOUCHED_AFTER_THE_ENGINE_CLOSE", w3d_user_residual_untouched_after_the_engine_close),
        ("WA_STOP_RACE_UNREADABLE_MODE_AFTER_OFF_SENDS_NOTHING_AND_LEAVES_A_DURABLE_RED", w_a_stop_race),
        ("WB_OWNED_SAME_NET_CLO_REDUCE_ONLY_SELL_3_SENDS", w_b_owned),
        ("WB_FOREIGN_SAME_NET_CLO_SENDS_NOTHING_NAMED_HOLD_NOTHING_FLATTENED", w_b_foreign),
        ("W4A_DUST_WHOLE_POSITION_CLOSE_SENDS_EXACT_FULL_CLOSE", w4a_whole_position),
        ("W4B_SUBMIN_REMAINDER_WITH_RESIDUAL_IS_HELD_NOT_SENT_AS_A_PARTIAL", w4b_submin_remainder_is_held_not_sent),
        ("W4C_HELD_REMAINDER_RESOLVED_BY_WHOLE_POSITION_CLOSE_WHEN_ACCOUNT_WOULD_GO_FLAT",
         w4c_resolved_by_whole_position_close_when_account_would_go_flat),
        ("W4D_NO_ENGINE_DUST_REMAINS_WHEN_THE_EXCHANGE_IS_FLAT", w4d_no_engine_dust_remains_when_exchange_is_flat),
        ("B_REAL_SEND_A_REDUCE_ONLY_CLOSE_REACHES_THE_SDK_EXCHANGE_CALLED_TRUE", b_real_send),
        ("B_REAL_SEND_PUBLIC_PATH_A_REDUCE_ONLY_CLOSE_REACHES_THE_SDK_VIA_SEND_IF_ALLOWED", b_real_send_public_path),
        ("W5_OLDER_TERMINAL_FILL_ID_DOES_NOT_BLOCK_A_FRESH_EXIT_ON_A_LIVE_SLEEVE", w5),
        ("W6A_UNREADABLE_EXCHANGE_NEVER_CLAIMS_FLAT", w6a_unreadable_exchange_never_claims_flat),
        ("W6B_WRONG_ACCOUNT_FLAT_READ_NEVER_CLAIMS_FLAT_AND_THE_CLOSE_IS_SENT",
         w6b_wrong_account_flat_read_never_claims_flat_and_close_is_sent),
        ("W6C_WRONG_ACCOUNT_EXCHANGE_REJECT_NEVER_ZEROES_THE_SLEEVE", w6c_wrong_account_exchange_reject_never_zeroes_the_sleeve),
        ("W7_HELD_DUST_ON_THE_SAME_FILL_ID_IS_NOT_CONSUMED", w7_held_same_fill_is_not_consumed),
        ("W8_ABSENT_KEY_IN_A_PARTIAL_LEDGER_IS_UNKNOWN_NO_FABRICATED_SLEEVE", w8_absent_key_in_a_partial_ledger_is_unknown),
        ("W9_TWO_SIMULTANEOUS_STALE_REPLAYS_PRODUCE_EXACTLY_ONE_NO_SEND", w9),
        ("RESTART_CONSUMED_EXIT_INTENT_AGAINST_FLAT_LEDGER_AND_FLAT_EXCHANGE_OPENS_NOTHING",
         restart_consumed_exit_never_opens_a_position),
    ]
    for nm, fn in witnesses:
        case(nm, fn)
    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    if failed:
        print("FAILED: " + ", ".join(failed))
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
