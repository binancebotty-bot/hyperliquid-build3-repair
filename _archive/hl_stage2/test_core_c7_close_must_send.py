#!/usr/bin/env python3
"""C7 close-must-send witnesses (tests FIRST; written before the Core predicate exists).

Source of the witnesses: Reviewer's C4a plan, PR #8 on binancebotty-bot/hermes-gpt-control, comments 6506577678 and
6506663891 (W1..W9), plus the commit-4 failure shapes (B_REAL_SEND, restart with a stale/consumed exit intent).

The rule under test: an EXIT/REDUCE intent is refused with the named no-send
SEND_NOT_ATTEMPTED_STALE_OR_CONSUMED_FLAT_SLEEVE ONLY when its exact wallet+coin engine sleeve is PROVEN flat/absent AND
(the fill is PROVEN stale replay OR was already terminally consumed). Everything else keeps the existing close behaviour:
a close of an open sleeve is never refused by this gate (netting closes that raise gross exposure, a user residual on the
coin, whole-position dust, ...).

Real ownership gate and real final-wire validator: neither is patched. Only DATA sources are faked: the fake exchange, the
fresh exchange-net read, the persisted exchange snapshot and the asset metadata. Own temp state dir; offline; testnet.

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

    def __init__(self, replies=None):
        self.calls = []
        self.replies = list(replies or [])
        self._lock = threading.Lock()

    def update_leverage(self, leverage, name, is_cross=True):
        return {"status": "ok"}

    def order(self, coin, is_buy, size, px, tif, reduce_only=False, cloid=None):
        with self._lock:
            self.calls.append({"coin": coin, "is_buy": is_buy, "size": float(size), "px": px, "reduce_only": reduce_only,
                               "cloid": None if cloid is None else str(cloid)})
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


def make_gateway(ex, ledger, net, account=ACCOUNT, snapshot=True):
    """A real SenderGateway; the REAL _pre_send_ownership_gate, _validate_final_wire_order, _close_wire_plan and
    send path run. Only data sources are replaced."""
    gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), ledger)
    gw._resolve_coin = lambda coin: dict(RESOLVED)
    gw._get_exchange_client = lambda *a, **k: ex
    gw._exchange_client_has_symbol = lambda *a, **k: True
    gw._pre_exchange_asset_safety = lambda *a, **k: (True, {})
    gw._exchange_client_for_coin = lambda coin: (ex, "BTC")
    gw._follower_order_account_for_proof = lambda *a, **k: account
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


def sleeve_of(ledger, wallet):
    row = ((ledger.data.get("by_wallet") or {}).get(wallet) or {}).get(COIN)
    return None if row is None else float(row.get("signed_size"))


# ======================================================================================= W1 stale replay, flat sleeve
def w1():
    led, ex, net = new_ledger(), FakeExchange(), [0.0]
    gw = make_gateway(ex, led, net)
    it = exit_intent(led, A, "SELL", 2.0, "w1-f", 2.0, source="WS_SNAPSHOT_REPLAY", ts=1)
    set_sleeve(led, A, 0.0)                                          # the position is gone: loaded, explicit 0
    ok, status = gw.send_if_allowed(it)
    rows = recon_rows("w1-f")
    return (not ok and status == NAME and not ex.calls and len(rows) == 1 and len(named_rows("w1-f")) == 1
            and str(rows[0].get("engine_can_send")) in ("False", "false", "0", "")), \
        "ok=%r status=%r calls=%d rows=%r" % (ok, status, len(ex.calls), [(r.get("status"), r.get("terminal_state")) for r in rows])


# ======================================================================================= W2 netted opposite-leader reduction
def w2():
    led, ex, net = new_ledger(), FakeExchange(), [-5.0]
    gw = make_gateway(ex, led, net)
    set_sleeve(led, B, -15.0)                                        # leader B short 15: exchange net = +10 - 15 = -5
    it = exit_intent(led, A, "SELL", 10.0, "w2-f", 10.0)
    ok, status = gw.send_if_allowed(it)
    return ok and len(ex.calls) == 1 and abs(ex.calls[0]["size"] - 10.0) < 1e-9 and ex.calls[0]["reduce_only"] is False, \
        "ok=%r status=%r calls=%r" % (ok, status, ex.calls)


def w2b():
    led, ex, net = new_ledger(), FakeExchange(), [5.0]
    gw = make_gateway(ex, led, net)
    set_sleeve(led, B, -5.0)                                         # leader B short 5: exchange net = +10 - 5 = +5
    it = exit_intent(led, A, "SELL", 10.0, "w2b-f", 10.0)
    ok, status = gw.send_if_allowed(it)
    return ok and len(ex.calls) == 1 and abs(ex.calls[0]["size"] - 10.0) < 1e-9, "ok=%r status=%r calls=%r" % (ok, status, ex.calls)


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
    led, ex, net = new_ledger(), FakeExchange(), [5.05]   # engine +0.05 ($5) with a user +5 residual
    gw = make_gateway(ex, led, net)
    it = exit_intent(led, A, "SELL", 0.05, "w4b-f", 0.05)
    ok, status = gw.send_if_allowed(it)
    sub_min = [x for x in ex.calls if x["size"] * PX < MIN_USD - 1e-9]
    return not sub_min and not ok, "ok=%r status=%r calls=%r" % (ok, status, ex.calls)


def w4c_resolved_by_whole_position_close_when_account_would_go_flat():
    led, ex, net = new_ledger(), FakeExchange(), [5.05]
    gw = make_gateway(ex, led, net)
    gw.send_if_allowed(exit_intent(led, A, "SELL", 0.05, "w4c-f1", 0.05))        # held / refused: sub-minimum with a residual
    net[0] = 0.05                                                              # the user residual is gone: engine's 0.05 is the whole position
    before = len(ex.calls)
    ok, status = gw.send_if_allowed(exit_intent(led, A, "SELL", 0.05, "w4c-f2", 0.05))
    new = ex.calls[before:]
    return ok and len(new) == 1 and abs(new[0]["size"] - 0.05) < 1e-9 and new[0]["reduce_only"] is True, \
        "ok=%r status=%r new_calls=%r" % (ok, status, new)


def w4d_no_engine_dust_remains_when_exchange_is_flat():
    led, ex, net = new_ledger(), FakeExchange(), [5.05]
    gw = make_gateway(ex, led, net)
    gw.send_if_allowed(exit_intent(led, A, "SELL", 0.05, "w4d-f1", 0.05))        # held
    net[0] = 0.0                                                               # the asset is flat on the exchange
    before = len(ex.calls)
    gw.send_if_allowed(exit_intent(led, A, "SELL", 0.05, "w4d-f2", 0.05))
    for nm in ("clear_close_escalations", "clear_trackb_escalations"):           # the periodic double-flat clear, either name
        fn = getattr(gw, nm, None)
        if callable(fn):
            fn()
    esc = c.load_json(c.CLOSE_ESCALATIONS_FILE, {}) if hasattr(c, "CLOSE_ESCALATIONS_FILE") else {}
    held = {}
    for p in TMP.glob("*.json"):
        if any(k in p.name.lower() for k in ("dust", "held", "remainder")):
            held.update(c.load_json(p, {}) or {})
    sl = sleeve_of(led, A)
    return (sl is not None and abs(sl) < 1e-9 and not held and not [v for v in (esc or {}).values() if v.get("state") == "OPEN"]
            and len(ex.calls) == before), \
        "sleeve=%r held=%r esc=%r new_calls=%d" % (sl, held, esc, len(ex.calls) - before)


# ======================================================================================= B_REAL_SEND shape
def b_real_send():
    led, ex, net = new_ledger(), FakeExchange(), [0.05]
    gw = make_gateway(ex, led, net)
    it = exit_intent(led, A, "SELL", 0.05, "breal-f", 0.05)
    ok, status, res = gw._send_real(it)
    return ok and len(ex.calls) == 1 and ex.calls[0]["reduce_only"] is True and (res or {}).get("exchange_called", True) is not False, \
        "ok=%r status=%r calls=%r exchange_called=%r" % (ok, status, ex.calls, (res or {}).get("exchange_called"))


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
    return status != NAME and not named_rows("w6a-f") and sl is not None and abs(sl - 2.0) < 1e-9, \
        "ok=%r status=%r sleeve=%r" % (ok, status, sl)


def w6b_wrong_account_flat_read_never_claims_flat_and_close_is_sent():
    led, ex, net = new_ledger(), FakeExchange(), [0.0]
    gw = make_gateway(ex, led, net, account=OTHER_ACCOUNT, snapshot=False)
    gw._persisted_exchange_positions = lambda: ({"BTC": 2.0}, "")            # the engine's own account snapshot: still +2
    it = exit_intent(led, A, "SELL", 2.0, "w6b-f", 2.0)
    ok, status = gw.send_if_allowed(it)
    sl = sleeve_of(led, A)
    return status != NAME and sl is not None and abs(sl - 2.0) < 1e-9 and ok and len(ex.calls) == 1, \
        "ok=%r status=%r sleeve=%r calls=%r" % (ok, status, sl, ex.calls)


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
    (led.data.get("by_wallet") or {}).pop(A, None)                            # the wallet is simply missing from the loaded map
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
    gate, out = threading.Barrier(2), []

    def go():
        gate.wait()
        out.append(gw.send_if_allowed(it))

    ts = [threading.Thread(target=go) for _ in range(2)]
    [t.start() for t in ts]
    [t.join(30) for t in ts]
    return len(named_rows("w9-f")) == 1 and not ex.calls, \
        "named_rows=%d calls=%d results=%r" % (len(named_rows("w9-f")), len(ex.calls), out)


# ======================================================================================= restart: consumed exit vs flat everything
def restart_consumed_exit_never_opens_a_position():
    led, ex, net = new_ledger(), FakeExchange(), [2.0]
    gw1 = make_gateway(ex, led, net)
    it = exit_intent(led, A, "SELL", 2.0, "rs-f", 2.0)
    ok1, st1 = gw1.send_if_allowed(it)                                        # the close goes out and fills
    set_sleeve(led, A, 0.0)
    net[0] = 0.0                                                              # sleeve flat AND exchange flat
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
        ("W4A_DUST_WHOLE_POSITION_CLOSE_SENDS_EXACT_FULL_CLOSE", w4a_whole_position),
        ("W4B_SUBMIN_REMAINDER_WITH_RESIDUAL_IS_HELD_NOT_SENT_AS_A_PARTIAL", w4b_submin_remainder_is_held_not_sent),
        ("W4C_HELD_REMAINDER_RESOLVED_BY_WHOLE_POSITION_CLOSE_WHEN_ACCOUNT_WOULD_GO_FLAT",
         w4c_resolved_by_whole_position_close_when_account_would_go_flat),
        ("W4D_NO_ENGINE_DUST_REMAINS_WHEN_THE_EXCHANGE_IS_FLAT", w4d_no_engine_dust_remains_when_exchange_is_flat),
        ("B_REAL_SEND_A_REDUCE_ONLY_CLOSE_REACHES_THE_SDK_EXCHANGE_CALLED_TRUE", b_real_send),
        ("W5_OLDER_TERMINAL_FILL_ID_DOES_NOT_BLOCK_A_FRESH_EXIT_ON_A_LIVE_SLEEVE", w5),
        ("W6A_UNREADABLE_EXCHANGE_NEVER_CLAIMS_FLAT", w6a_unreadable_exchange_never_claims_flat),
        ("W6B_WRONG_ACCOUNT_FLAT_READ_NEVER_CLAIMS_FLAT_AND_THE_CLOSE_IS_SENT",
         w6b_wrong_account_flat_read_never_claims_flat_and_close_is_sent),
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
