#!/usr/bin/env python3
"""CC-1 close-scenario suite: M1, CS-I1..I4, R1, I05/I06/I22/I23, CH-4/8/9.
Testnet/offline ONLY. A test-only commit does not certify a fix or provide executed evidence.

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
import time
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

# C7-WO-1-R95: the sender refuses unless the engine ALREADY owns the machine-wide lease.
# Acquire it as the real engine does at start, in the ISOLATED temp lock path above.
c.acquire_global_instance_lock(TMP / "state")

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
        self.physical_net = None

    def update_leverage(self, leverage, name, is_cross=True):
        return {"status": "ok"}

    def order(self, coin, is_buy, size, px, tif, reduce_only=False, cloid=None):
        with self._lock:
            self.calls.append({"coin": coin, "is_buy": is_buy, "size": float(size), "px": px, "reduce_only": reduce_only,
                               "cloid": None if cloid is None else str(cloid)})
            if self.replies:
                return self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
            if self.physical_net is not None:
                self.physical_net[0] += float(size) * (1 if is_buy else -1)
            return filled(size, px, oid=len(self.calls) + int(getattr(self, "oid_base", 0)))

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
    ex.physical_net = net
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


def exit_intent(ledger, wallet, side, size, fid, sleeve, source="POLL", ts=None, start=None):
    """A real, send-authorised EXIT intent built while the wallet sleeve holds ``sleeve`` (signed)."""
    set_sleeve(ledger, wallet, sleeve)
    fill = c.LeaderFill(fid, wallet, COIN, side, PX, size, ts if ts is not None else c.utc_now_ms(), source)
    if start is not None:
        # R81: the leader position BEFORE the fill. R81 fixtures declare it explicitly; the
        # production ingest copies it from the exchange row into raw["startPosition"].
        fill.raw["startPosition"] = str(start)
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


def send_rows(fid):
    """Every send_attempts row for this intent, oldest first: the write-ahead pending_send rows and their finals."""
    p = c.SEND_ATTEMPTS_CSV
    if not p.exists():
        return []
    with p.open("r", newline="", encoding="utf-8-sig") as fh:
        return [r for r in csv.DictReader(fh) if r.get("intent_id") == fid]


def named_rows(fid):
    return [r for r in recon_rows(fid) if NAME in (r.get("terminal_state"), r.get("status"))]


def red_for(fid):
    rows = c.load_json(c.CLOSE_ESCALATIONS_FILE, {})
    return [r for r in (rows.values() if isinstance(rows, dict) else ())
            if isinstance(r, dict) and r.get("state") == "OPEN"
            and r.get("leader_fill_id") == fid and r.get("coin") == COIN]


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
    a_sleeve, b_sleeve, net_before = sleeve_of(led, A), sleeve_of(led, B), net[0]
    ok, status = gw.send_if_allowed(it)
    # C7-WO-1-R99: production DOES distinguish close from entry (SenderGateway._reduce_only_for_intent),
    # but the wire reduce_only flag is decided by whether the close fits the account NET, so here the
    # close intent is sent WITHOUT reduce-only: 10 exceeds the account net 5, and as an ENTRY for leader
    # B's sleeve it must fit entry sizing (B's remaining capacity = 15 - 5 = 10).
    order = ex.calls[0] if len(ex.calls) == 1 else None
    close_intent = c.SenderGateway._reduce_only_for_intent(it) is True
    entry_sized = (order is not None and order["reduce_only"] is False
                   and abs(order["size"]) > abs(net_before)                            # a reduce-only close above the net cannot exist
                   and abs(order["size"]) <= abs(b_sleeve) - abs(net_before))          # entry fits B's sleeve capacity
    close_within_sleeve = all(abs(call["size"]) <= abs(a_sleeve)
                              for call in ex.calls if call["reduce_only"] is True)
    return (ok and len(ex.calls) == 1 and abs(ex.calls[0]["size"] - 10.0) < 1e-9
            and ex.calls[0]["reduce_only"] is False and abs(net[0] + 15.0) < 1e-9
            and close_intent and entry_sized and close_within_sleeve), \
        "ok=%r status=%r calls=%r close_intent=%r entry_sized=%r close_within_sleeve=%r sleeves=%r/%r net_before=%r" % (
            ok, status, ex.calls, close_intent, entry_sized, close_within_sleeve, a_sleeve, b_sleeve, net_before)


# ======================================================================================= W3 live sleeve / user residual
def w3a():
    led, ex, net = new_ledger(), FakeExchange(), [2.0]
    gw = make_gateway(ex, led, net)
    it = exit_intent(led, A, "SELL", 1.0, "w3a-f", 2.0, start=2.0)
    ok, status = gw.send_if_allowed(it)
    return (ok and len(ex.calls) == 1 and ex.calls[0]["reduce_only"] is True
            and abs(ex.calls[0]["size"] - it.copy_size) < 1e-9 and abs(net[0] - 1.0) < 1e-9), \
        "ok=%r status=%r calls=%r copy_size=%r" % (ok, status, ex.calls, it.copy_size)


def w3b_user_residual():
    led, ex, net = new_ledger(), FakeExchange(), [5.5]   # engine +0.5, a user-managed +5 on the same coin
    gw = make_gateway(ex, led, net)
    it = exit_intent(led, A, "SELL", 0.5, "w3b-f", 0.5, start=0.5)
    ok, status = gw.send_if_allowed(it)
    return (ok and len(ex.calls) == 1 and abs(ex.calls[0]["size"] - it.copy_size) < 1e-9
            and ex.calls[0]["reduce_only"] is True and abs(net[0] - 5.0) < 1e-9), \
        "ok=%r status=%r calls=%r" % (ok, status, ex.calls)


# ======================================================================================= W4 dust
def w4a_whole_position():
    led, ex, net = new_ledger(), FakeExchange(), [0.05]
    gw = make_gateway(ex, led, net)
    it = exit_intent(led, A, "SELL", 0.05, "w4a-f", 0.05, start=0.05)
    ok, status = gw.send_if_allowed(it)
    return (ok and len(ex.calls) == 1 and abs(ex.calls[0]["size"] - 0.05) < 1e-9
            and ex.calls[0]["reduce_only"] is True and abs(net[0]) < 1e-9), \
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
    gw.send_if_allowed(exit_intent(led, A, "SELL", 0.05, "w4c-f1", 0.05, start=0.05))   # held / refused: sub-minimum with a residual
    net[0] = 0.05                                                              # the user residual is gone: engine's 0.05 is the whole position
    before = len(ex.calls)
    ok, status = gw.send_if_allowed(exit_intent(led, A, "SELL", 0.05, "w4c-f2", 0.05, start=0.05))
    new = ex.calls[before:]
    return ok and len(new) == 1 and abs(new[0]["size"] - 0.05) < 1e-9 and new[0]["reduce_only"] is True, \
        "ok=%r status=%r new_calls=%r" % (ok, status, new)


def w4d_no_engine_dust_remains_when_exchange_is_flat():
    """CS-I4/I23: a full EXIT of an owned 0.105 BTC sleeve (requested 0.100)
    cannot leave 0.005 BTC/$0.50 inaccessible dust without an OPEN owed close.
    Assert the independent physical exchange end state rather than plan labels."""
    led, ex, net = new_ledger(), FakeExchange(), [0.105]
    gw = make_gateway(ex, led, net)
    it = exit_intent(led, A, "SELL", 0.100, "w4d-f", 0.105, start=0.1)
    ok, status = gw.send_if_allowed(it)
    exact_flat_send = (ok and len(ex.calls) == 1
                       and abs(ex.calls[0]["size"] - 0.105) < 1e-9
                       and abs(net[0]) < 1e-9)
    unresolved_holds = (not ok and not ex.calls and abs(net[0] - 0.105) < 1e-9
                        and bool(red_for("w4d-f")))
    return exact_flat_send or unresolved_holds, \
        "status=%r sdk=%r exchange_after=%r red=%r" % (status, ex.calls, net[0], red_for("w4d-f"))


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
    return (not ok and not ex.calls and bool(red_for("w6a-f")) and sl is not None and abs(sl - 2.0) < 1e-9), \
        "ok=%r status=%r sleeve=%r" % (ok, status, sl)


def w6b_wrong_account_flat_read_never_claims_flat_and_close_is_sent():
    led, ex, net = new_ledger(), FakeExchange(), [0.0]
    gw = make_gateway(ex, led, net, account=OTHER_ACCOUNT, snapshot=False)
    gw._persisted_exchange_positions = lambda: ({"BTC": 2.0}, "")            # the engine's own account snapshot: still +2
    it = exit_intent(led, A, "SELL", 2.0, "w6b-f", 2.0)
    ok, status = gw.send_if_allowed(it)
    sl = sleeve_of(led, A)
    return (not ok and not ex.calls and bool(red_for("w6b-f")) and sl is not None and abs(sl - 2.0) < 1e-9), \
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
    return (not ok and not ex.calls and not named_rows("w7-f") and bool(red_for("w7-f"))), \
        "ok=%r status=%r" % (ok, status)


# ======================================================================================= W8 absent key, partial ledger
def w8_absent_key_in_a_partial_ledger_is_unknown():
    led, ex, net = new_ledger(), FakeExchange(), [0.0]
    gw = make_gateway(ex, led, net)
    it = exit_intent(led, A, "SELL", 1.0, "w8-f", 1.0, source="WS_SNAPSHOT_REPLAY", ts=1)
    (led.data.get("by_wallet") or {}).pop(A, None)                            # the wallet is simply missing from the loaded map
    ok, status = gw.send_if_allowed(it)
    fabricated = ((led.data.get("by_wallet") or {}).get(A) or {}).get(COIN)
    return (not ok and not ex.calls and status != NAME and not named_rows("w8-f")
            and fabricated is None and bool(red_for("w8-f"))), \
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
    return (len(out) == 2 and all(not x[0] for x in out)
            and len(named_rows("w9-f")) == 1 and not ex.calls), \
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
    return (ok1 and not ok2 and st2 == NAME and not new and abs(net[0]) < 1e-9
            and len(named_rows("rs-f")) == 1), \
        "first=%r/%r replay=%r/%r new_calls=%r" % (ok1, st1, ok2, st2, new)



# ======================================================================================= CE1/CE2, event loss and physical-wire bypass matrix
def _held_with_physical_proof(fid, ok, status, ex, physical, expected):
    """R1/CS-I3: check durable OPEN and unchanged actual, never a local return alone."""
    rows = recon_rows(fid)
    return (not ok and not ex.calls and abs(physical[0] - expected) < 1e-9
            and bool(red_for(fid)) and bool(rows)
            and not str(status).startswith(("BLOCKED_OFF", "MASTER_REAL_ORDERS_OFF", "INTENT_NOT_SEND_ALLOWED")))


def ce1_stale_owned_does_not_eat_foreign():
    """CS-I2/I3, R1 - restored with a TRUTHFUL sleeve (CE1 3a).

    Ownership is engine +0.5, foreign +4.5, fresh exchange net +5.0. The sleeve carries the
    PROVEN engine size (0.5), so the close proof can justify a reduce-only close of at most the
    sleeve: the engine closes its own 0.5 and the foreign 4.5 is untouched. HOLD is NOT the
    expectation here - a truthful sleeve is a case the proof can reason about, so closes stay
    sacred. The overstated-sleeve case (ledger says 2.0 while proven is 0.5) needs a provenance
    -proven owned figure the close proof does not yet have; it stays an OPEN RISK, not a
    silently-relaxed expectation. A successful close opens no RED row, so the owed/RED half
    cannot be witnessed here either - only its absence is asserted."""
    led, ex, net = new_ledger(), FakeExchange(), [5.0]
    gw = make_gateway(ex, led, net)
    # TRUE ownership: engine +0.5, foreign +4.5. The sleeve carries the PROVEN engine size.
    it = exit_intent(led, A, "SELL", 2.0, "ce1-f", 0.5)
    ok, status = gw.send_if_allowed(it)
    # A close that SUCCEEDS opens no escalation row, so the owed/RED witness can only exist on a
    # HOLD. Asserting its ABSENCE here is the honest form; the owed/RED half needs the
    # overstated-sleeve hook (3b) and stays an OPEN RISK, not a silently-relaxed expectation.
    red = red_for("ce1-f")
    return (ok and len(ex.calls) == 1 and ex.calls[0]["reduce_only"] is True
            and abs(ex.calls[0]["size"] - 0.5) < 1e-9
            and isinstance(net[0], (int, float)) and abs(net[0] - 4.5) < 1e-9
            and abs(sleeve_of(led, A) - 0.5) < 1e-9
            and red == []), (
        "status=%r sdk=%r net=%r sleeve=%r owned=0.5 foreign=4.5 red=%r"
        % (status, ex.calls, net[0], sleeve_of(led, A), red))


def ce2_bad_master_does_not_eat_foreign():
    """CS-I3/R1/I22: false matching persisted snapshot cannot authenticate
    the SDK order account. Foreign +5, ledger +1; reader != signer."""
    led, ex, net = new_ledger(), FakeExchange(), [5.0]
    gw = make_gateway(ex, led, net, account=OTHER_ACCOUNT, snapshot=False)
    gw._persisted_exchange_positions = lambda: ({"BTC": 1.0}, "")
    it = exit_intent(led, A, "SELL", 1.0, "ce2-f", 1.0)
    ok, status = gw.send_if_allowed(it)
    return _held_with_physical_proof("ce2-f", ok, status, ex, net, 5.0), \
        "status=%r sdk=%r net=%r" % (status, ex.calls, net[0])


def ce1b_refused_close_owes_a_red_and_leaves_the_foreign_residual_untouched():
    """CC1-B-RULING-2114 item 3: a REFUSED close is OWED, and a refusal - unlike the CE1 SUCCESS - can witness
    it. Engine sleeve +2.0, foreign residual +4.5, fresh exchange net +6.5. The close proof refuses because the
    account the SDK would sign for is NOT the account the net was read from (an account mismatch), so nothing
    reaches the wire. All four facts are asserted from durable state, never from the return value alone:
      (a) REFUSED and RESTING: no wire call, and the intent still rests at the LEADER price, unmodified;
      (b) a RED escalation row EXISTS for this fill - the owed obligation written by the refusal journal;
      (c) the foreign units are UNTOUCHED: the exchange net is unchanged and the residual is still a number;
      (d) the gateway holds a REAL audit writer, so _journal_authorised_close_refusal writes instead of
          raising (ruling item 7: any gateway built with object.__new__ must supply `audit`).
    The refusal reason is an EXISTING one - SEND_NOT_ATTEMPTED_CLOSE_PROOF_HOLD from _close_wire_plan - not a
    new reason and not a new policy."""
    engine, foreign = 2.0, 4.5
    led, ex, net = new_ledger(), FakeExchange(), [engine + foreign]
    gw = make_gateway(ex, led, net, account=OTHER_ACCOUNT, snapshot=False)
    gw._persisted_exchange_positions = lambda: ({"BTC": engine}, "")   # our own account: +2, never the +6.5 read
    # (d) the writer is the PRODUCTION AuditLogWriter with both journal methods, not a stub that would raise.
    real_audit = (isinstance(gw.audit, c.AuditLogWriter)
                  and callable(getattr(gw.audit, "append_reconciliation", None))
                  and callable(getattr(gw.audit, "has_fill_row", None)))
    fid = "ce1b-f"
    it = exit_intent(led, A, "SELL", engine, fid, engine)
    ok, status = gw.send_if_allowed(it)
    red = red_for(fid)
    # (d) the refusal journal RAN: the RED JSON on disk carries this fill. _journal_authorised_close_refusal only
    # adds the supplemental reconciliation row when the dispatcher has not already written a row for the fill
    # (has_fill_row); the ownership-gate refusal above did, so the durable RED file is the witness here.
    on_disk = c.load_json(c.CLOSE_ESCALATIONS_FILE, {})
    persisted = [r for r in (on_disk.values() if isinstance(on_disk, dict) else ())
                 if isinstance(r, dict) and r.get("leader_fill_id") == fid and r.get("state") == "OPEN"]
    net_after = net[0]
    residual = (net_after - engine) if isinstance(net_after, (int, float)) else None
    return (not ok and not ex.calls                                        # (a) refused, nothing on the wire
            and abs(float(it.fill.price) - PX) < 1e-9                       # (a) still resting at the LEADER price
            and it.decision == "EXIT_ALLOWED"                               # (a) the obligation is not consumed
            and len(red) == 1 and red[0].get("state") == "OPEN"             # (b) the owed RED row exists
            and red[0].get("reason") == status
            and len(persisted) == 1                                         # (d) the journal write persisted, no raise
            and residual is not None and abs(residual - foreign) < 1e-9     # (c) foreign residual still a number
            and abs(net_after - (engine + foreign)) < 1e-9                  # (c) the exchange net is unchanged
            and real_audit), (
        "ok=%r status=%r calls=%r leader_px=%r decision=%r red=%r persisted=%d net_after=%r foreign=%r "
        "sleeve=%r real_audit=%r" % (ok, status, ex.calls, it.fill.price, it.decision,
                                     [(r.get("state"), r.get("reason")) for r in red], len(persisted),
                                     net_after, residual, sleeve_of(led, A), real_audit))


def missing_fill_equal_coin_net_is_not_proof():
    """CS-I2/CH-9: net=ledger=+2 cannot certify A owns +2. Independent truth
    (known to test oracle only): A +0.5, FOREIGN +1.5, one fill is missing from
    persisted provenance. Missing trusted anchor/complete replay => HOLD RED."""
    led, ex, net = new_ledger(), FakeExchange(), [2.0]
    gw = make_gateway(ex, led, net)
    it = exit_intent(led, A, "SELL", 2.0, "event-loss-f", 2.0)
    ok, status = gw.send_if_allowed(it)
    return (_held_with_physical_proof("event-loss-f", ok, status, ex, net, 2.0)
            and abs(net[0] - 0.5 - 1.5) < 1e-9), \
        "status=%r sdk=%r net=%r independent_foreign=1.5" % (status, ex.calls, net[0])


def unresolved_owed_survives_restart():
    """I05/I06/R1: same persistent ledger reloaded into a fresh gateway;
    unreadable account keeps exactly the same OPEN owed obligation."""
    led, ex, net = new_ledger(), FakeExchange(), [None]
    gw = make_gateway(ex, led, net)
    it = exit_intent(led, A, "SELL", 1.0, "owed-restart-f", 1.0)
    c.atomic_write_json(led.path, led.data)
    ok, status = gw.send_if_allowed(it)
    before = red_for("owed-restart-f")
    led2 = c.ManualLedger(path=led.path)
    gw2 = make_gateway(ex, led2, net)
    ok2, status2 = gw2.send_if_allowed(it)
    after = red_for("owed-restart-f")
    return (not ok and not ok2 and not ex.calls and len(before) == 1
            and len(after) == 1 and abs(sleeve_of(led2, A) - 1.0) < 1e-9), \
        "first=%r/%r second=%r/%r red=%r sdk=%r" % (ok, status, ok2, status2, after, ex.calls)


def bypass_door(n):
    """CS-I1/I2/I3: seven early-return paths cannot waive the final exchange
    ownership envelope. Inspect the real _close_wire_plan AND final-wire validator
    with an independently known +0.5 owned maximum (requested SELL2).
    This deliberately tests the final admissible physical order, NOT a return flag."""
    led, ex, account = new_ledger(), FakeExchange(), [0.4]
    gw = make_gateway(ex, led, account)
    it = exit_intent(led, A, "SELL", 2.0, "door%d-f" % n, 0.5)
    dec, timing, options = 3, {}, {}
    old = os.environ.get("HL_LIVE_CLOSE_TO_TARGET")
    try:
        if n == 1:  # unknown precision
            dec = None
        elif n == 2:  # dust flag used to bypass safe sizing
            timing["dust_close_below_min_notional"] = True
        elif n == 3:  # ledger absent
            gw.ledger = None
        elif n == 4:  # config toggle disabled
            os.environ["HL_LIVE_CLOSE_TO_TARGET"] = "0"
        elif n == 5:  # exchange actual unreadable
            gw._fresh_exchange_net = lambda coin: None
        elif n == 6:  # lagged ledger + min-exception fallthrough
            options["ledger_may_lag"] = True
        elif n == 7:  # trim below min -> legacy full-size fallthrough
            account[0] = -1.45
        reduce_only, planned, skip = gw._close_wire_plan(
            it, 2.0, dec, lambda size: abs(size * PX) >= MIN_USD,
            timing, **options)
        wire_ok = False
        if not skip and planned > 0:
            wire_ok, _block = gw._validate_final_wire_order(
                it, dict(RESOLVED), COIN, planned, PX, dict(timing))
        admitted = planned if wire_ok and not skip else 0.0
        unknown = n in (1, 3, 5)
        return (admitted <= 0.5 + 1e-9 and (not unknown or admitted == 0.0)), \
            "door=%d ro=%r proposed=%r skip=%r wire_ok=%r admitted=%r owned=0.5" % (
                n, reduce_only, planned, skip, wire_ok, admitted)
    finally:
        if old is None:
            os.environ.pop("HL_LIVE_CLOSE_TO_TARGET", None)
        else:
            os.environ["HL_LIVE_CLOSE_TO_TARGET"] = old




def r81_share_of_roleader_position():
    """R81 (CS-I1/I2): the close copies the SHARE of the leader position this fill closed.

    Leader holds 1000 and closes 1 (0.1 pct). A 2.0 follower sleeve must close 0.002 - not 1.0
    (leader units leaking into a follower-sized sleeve) and not 2.0 (the old full-sleeve exit)."""
    led, ex, net = new_ledger(), FakeExchange(), [2.0]
    it = exit_intent(led, A, "SELL", 1.0, "r81a-f", 2.0, start=1000.0)
    return abs(it.copy_size - 0.002) < 1e-9, (
        "copy_size=%r expected 0.002 (share 1/1000 of a 2.0 sleeve)" % it.copy_size)


def r81_missing_start_is_full_sleeve():
    """R81: startPosition absent => FULL sleeve (old behaviour). Over-close is the safe side and
    a close is never dropped, so an unknown share must never shrink the close."""
    led, ex, net = new_ledger(), FakeExchange(), [2.0]
    it = exit_intent(led, A, "SELL", 1.0, "r81b-f", 2.0)
    return abs(it.copy_size - 2.0) < 1e-9, (
        "copy_size=%r expected 2.0 (no startPosition -> full sleeve)" % it.copy_size)


def r81_whole_leader_close_is_full_sleeve():
    """R81: the leader closes its entire 1.0 position (start 1.0, fill 1.0) => fraction 1 =>
    exactly the full sleeve, no dust left behind."""
    led, ex, net = new_ledger(), FakeExchange(), [2.0]
    it = exit_intent(led, A, "SELL", 1.0, "r81c-f", 2.0, start=1.0)
    return abs(it.copy_size - 2.0) < 1e-9, (
        "copy_size=%r expected 2.0 (whole leader close)" % it.copy_size)


def r81_half_leader_close_is_half_sleeve():
    """R81: the leader closes half (start 2.0, fill 1.0) => half the sleeve."""
    led, ex, net = new_ledger(), FakeExchange(), [2.0]
    it = exit_intent(led, A, "SELL", 1.0, "r81d-f", 2.0, start=2.0)
    return abs(it.copy_size - 1.0) < 1e-9, "copy_size=%r expected 1.0 (half of sleeve)" % it.copy_size


# ======================================== R81 SIGN: an ADD is not a close (wire-level)
def r81_sign_flip_through_zero():
    """(a) Leader LONG +5 SELLs 8 and flips to -3. Our sleeve is +2, so the whole sleeve closes: wire SELL 2.0
    reduce-only, net 0. The wire size is asserted, never intent.copy_size."""
    led, ex, net = new_ledger(), FakeExchange(), [2.0]
    gw = make_gateway(ex, led, net)
    it = exit_intent(led, A, "SELL", 8.0, "r81s-a1-f", 2.0, start=5.0)
    ok, status = gw.send_if_allowed(it)
    return (ok and len(ex.calls) == 1 and abs(ex.calls[0]["size"] - 2.0) < 1e-9
            and ex.calls[0]["is_buy"] is False and ex.calls[0]["reduce_only"] is True
            and abs(net[0]) < 1e-9), \
        "ok=%r status=%r calls=%r net=%r" % (ok, status, ex.calls, net)


def r81_sign_add_to_short_never_reaches_the_wire():
    """(a) NEGATIVE: leader SHORT -5 SELLs 2 - the leader is ADDING to a short. Nothing was closed, so nothing may
    be sent: no wire call at all, a terminal SEND_NOT_ATTEMPTED_INVALID_SIZE, net and sleeve untouched."""
    led, ex, net = new_ledger(), FakeExchange(), [2.0]
    gw = make_gateway(ex, led, net)
    it = exit_intent(led, A, "SELL", 2.0, "r81s-a2-f", 2.0, start=-5.0)
    ok, status = gw.send_if_allowed(it)
    return (not ok and status == "SEND_NOT_ATTEMPTED_INVALID_SIZE" and ex.calls == []
            and abs(net[0] - 2.0) < 1e-9 and abs(sleeve_of(led, A) - 2.0) < 1e-9), \
        "ok=%r status=%r calls=%r net=%r sleeve=%r" % (ok, status, ex.calls, net, sleeve_of(led, A))


def r81_sign_chained_catchup():
    """(b) Three successive partial leader closes on a +10 sleeve. Each wire size is the SHARE of the sleeve the
    leader closed, applied to the ledger between fills: 2.0, 2.0, 6.0; net 10.0 -> 8.0 -> 6.0 -> 0.0."""
    led, ex, net = new_ledger(), FakeExchange(), [10.0]
    gw = make_gateway(ex, led, net)
    plan = [("r81s-b1-f", 1.0, 5.0, 10.0), ("r81s-b2-f", 1.0, 4.0, 8.0), ("r81s-b3-f", 2.5, 2.5, 6.0)]
    got = []
    for fid, size, start, sleeve in plan:
        it = exit_intent(led, A, "SELL", size, fid, sleeve, start=start)
        ok, status = gw.send_if_allowed(it)
        if not ok or len(ex.calls) != 1:
            return False, "fid=%s ok=%r status=%r calls=%r got=%r" % (fid, ok, status, ex.calls, got)
        wire = ex.calls[0]
        if wire["is_buy"] is not False or wire["reduce_only"] is not True:
            return False, "fid=%s side/reduce_only wrong: %r" % (fid, wire)
        got.append(wire["size"])
        led.apply_copy_fill(it, {"side": "SELL", "size": wire["size"], "price": PX, "copy_fill_id": "cf-" + fid})
        ex.calls.clear()
    return (all(abs(g - w) < 1e-9 for g, w in zip(got, (2.0, 2.0, 6.0)))
            and abs(sleeve_of(led, A)) < 1e-9 and abs(net[0]) < 1e-9), \
        "wire=%r expected [2.0, 2.0, 6.0]; sleeve=%r net=%r" % (got, sleeve_of(led, A), net[0])


def r81_sign_rounding_at_size_decimals():
    """(c) Leader +3 SELLs 1 (share 1/3) on a +10 sleeve: copy 3.33333333 floors to 3.333 at sz_decimals=3 and
    3.33 at sz_decimals=2. The WIRE size is asserted; net keeps the remainder."""
    out = []
    for dec, want, want_net in ((3, 3.333, 6.667), (2, 3.33, 6.67)):
        led, ex, net = new_ledger(), FakeExchange(), [10.0]
        gw = make_gateway(ex, led, net)
        gw._resolve_coin = lambda coin, _d=dec: dict(RESOLVED, sz_decimals=_d)
        it = exit_intent(led, A, "SELL", 1.0, "r81s-c%d-f" % dec, 10.0, start=3.0)
        ok, status = gw.send_if_allowed(it)
        if not ok or len(ex.calls) != 1:
            return False, "dec=%d ok=%r status=%r calls=%r" % (dec, ok, status, ex.calls)
        if abs(ex.calls[0]["size"] - want) > 1e-9 or ex.calls[0]["reduce_only"] is not True:
            return False, "dec=%d wire=%r expected %r reduce_only" % (dec, ex.calls[0], want)
        if abs(net[0] - want_net) > 1e-6:
            return False, "dec=%d net=%r expected %r" % (dec, net[0], want_net)
        out.append((dec, ex.calls[0]["size"], round(net[0], 6)))
    return True, "ok=%r" % (out,)


def r81_sign_subminimum_residual_is_whole_close():
    """(d) Share 0.996 of a +10 sleeve leaves $4 of dust below the $10 minimum, so I23 rounds UP to the whole
    owned sleeve: wire 10.0, one call, no residue. Negative twin: share 1/30 closes 0.333 and leaves 9.667 owned."""
    led, ex, net = new_ledger(), FakeExchange(), [10.0]
    gw = make_gateway(ex, led, net)
    it = exit_intent(led, A, "SELL", 0.996, "r81s-d1-f", 10.0, start=1.0)
    ok, status = gw.send_if_allowed(it)
    if not (ok and len(ex.calls) == 1 and abs(ex.calls[0]["size"] - 10.0) < 1e-9
            and ex.calls[0]["reduce_only"] is True and abs(net[0]) < 1e-9):
        return False, "round-up ok=%r status=%r calls=%r net=%r" % (ok, status, ex.calls, net)
    led2, ex2, net2 = new_ledger(), FakeExchange(), [10.0]
    gw2 = make_gateway(ex2, led2, net2)
    it2 = exit_intent(led2, A, "SELL", 0.1, "r81s-d2-f", 10.0, start=3.0)
    ok2, status2 = gw2.send_if_allowed(it2)
    if not (ok2 and len(ex2.calls) == 1 and abs(ex2.calls[0]["size"] - 0.333) < 1e-9 and abs(net2[0] - 9.667) < 1e-6):
        return False, "partial ok=%r status=%r calls=%r net=%r" % (ok2, status2, ex2.calls, net2)
    return True, "round-up wire=10.0 net=0; partial wire=0.333 net=9.667"

# ============================================== CC1-B-RULING-CEILING-1920: split, never cap
def _ceiling_fixture(copy_size, fixed_notional=500.0, wallets=None, fid=None, oid_base=None):
    """A real gateway on a +10 owned sleeve whose account holds exactly that sleeve (so the close fits the net and is
    sent reduce-only). Only data sources are replaced: config scope, fixed_notional, the exposure read.
    ``oid_base`` isolates this witness's exchange order ids from every other witness's fill-ledger rows."""
    led, ex, net = new_ledger(), FakeExchange(), [10.0]
    if oid_base is not None:
        ex.oid_base = int(oid_base)
    gw = make_gateway(ex, led, net)
    it = exit_intent(led, A, "SELL", copy_size, fid or ("ceil-%s-f" % copy_size), 10.0)
    it.copy_size = float(copy_size)  # a close-lifecycle order may exceed our own sleeve (W2b shape)
    it.copy_notional = abs(float(copy_size) * PX)
    gw.cfg.wallets = lambda: ({A: {}, B: {}} if wallets is None else wallets)
    gw.cfg.fixed_notional = lambda w: fixed_notional
    # the ONE entry-cap code, wired exactly as the core wires it (sender.cap_source = the intent builder)
    capb = c.IntentBuilder(gw.cfg, led)
    capb.follower_exposure = lambda: {"ok": True, "total_usd": 0.0, "by_coin": {}}
    capb._resting = lambda: {}
    gw.cap_source = capb
    return led, ex, net, gw, it


def ceil_w2b_excess_is_clipped_to_entry_size():
    """(i) W2b at 200 pct of the sleeve: the wire shows the sleeve CLOSE (10, reduce-only) PLUS the excess as an ENTRY
    sized by fixed_notional (500 usd / 100 = 5 units), never 20 and never a clip of the close."""
    led, ex, net, gw, it = _ceiling_fixture(20.0, fixed_notional=500.0, fid="ceil-w2b-f", oid_base=1000)
    # CC1-B-SENDBACK2-2140(2): the excess may only follow a close PROVEN filled in full by the fill ledger.
    _record_owned_close_fill(gw, ex, 10.0)
    ok, status = gw.send_if_allowed(it)
    calls = ex.calls
    close_calls = [x for x in calls if x["reduce_only"] is True]
    entry_calls = [x for x in calls if x["reduce_only"] is False]
    return (ok and len(close_calls) == 1 and abs(close_calls[0]["size"] - 10.0) < 1e-9
            and len(entry_calls) == 1 and entry_calls[0]["size"] <= 10.0 + 1e-9
            and abs(entry_calls[0]["size"] - 5.01) < 1e-9
            and entry_calls[0]["is_buy"] is False), \
        "ok=%r status=%r calls=%r (want close 10 ro=True + entry 5 ro=False)" % (ok, status, calls)


def ceil_pure_close_never_reduced_by_any_cap():
    """(ii) A pure close at or under the sleeve is never reduced, at ANY cap setting: tiny total/asset caps and a tiny
    max_order_notional are set and the close still goes out whole and reduce-only. Closes are sacred."""
    led, ex, net, gw, it = _ceiling_fixture(8.0)
    gw.cfg.max_total_exposure = lambda: 1.0
    gw.cfg.max_asset_directional_exposure = lambda: 1.0
    gw.cfg.max_order_notional = lambda: 0.01
    ok, status = gw.send_if_allowed(it)
    return (ok and len(ex.calls) == 1 and abs(ex.calls[0]["size"] - 8.0) < 1e-9
            and ex.calls[0]["reduce_only"] is True), \
        "ok=%r status=%r calls=%r (want exactly one close of 8 ro=True under tiny caps)" % (ok, status, ex.calls)


def ceil_unknown_entry_sizing_is_a_loud_fault_and_the_close_still_sends():
    """(iii) Excess with entry sizing that CANNOT be computed (wallet not in config scope) is a LOUD fault row through
    the existing error path - not a pass, not a silent clip - and the close part still sends."""
    led, ex, net, gw, it = _ceiling_fixture(20.0, wallets={})
    ok, status = gw.send_if_allowed(it)
    faults = [r for r in recon_rows("ceil-20.0-f")
              if r.get("terminal_state") == "CEILING_EXCESS_ENTRY_SIZING_UNKNOWN"]
    return (ok and len(ex.calls) == 1 and abs(ex.calls[0]["size"] - 10.0) < 1e-9
            and ex.calls[0]["reduce_only"] is True and len(faults) == 1), \
        "ok=%r status=%r calls=%r faults=%r" % (ok, status, ex.calls,
                                               [(r.get("status"), r.get("terminal_state")) for r in faults])


def toctou_pre_send_ledger_moves_gives_zero_calls_and_terminalises_the_row():
    """TOCTOU: the close proof and the mode gate run BEFORE pre_send and are not rechecked after it. A pre_send
    callback that MOVES THE LEDGER NET while the LEASE IS KEPT must give ZERO exchange calls and must
    terminalise the pending_send row it wrote - never leave a pending row for an unsent order."""
    led, ex, net, gw, it = _ceiling_fixture(9.0)
    real = gw._place_order

    def move_then_send(exchange, sdk_coin, is_buy, size, limit_px, tif, reduce_only, timing=None,
                       started_key="", cloid=None, bypass_rate_limit_cooldown=False, pre_send=None,
                       intent=None, path="", **kw):
        def _move():
            aid = pre_send()
            set_sleeve(led, A, -6.0)   # the sleeve flipped under us after the proof; the lease is untouched
            net[0] = -6.0
            return aid
        return real(exchange, sdk_coin, is_buy, size, limit_px, tif, reduce_only, timing, started_key,
                    cloid=cloid, bypass_rate_limit_cooldown=bypass_rate_limit_cooldown,
                    pre_send=_move, intent=intent, path=path, **kw)

    gw._place_order = move_then_send
    ok, status = gw.send_if_allowed(it)
    rows = send_rows("ceil-9.0-f")
    return (not ok and not ex.calls and len(rows) == 2
            and rows[0].get("status") == "pending_send"
            and rows[-1].get("status") == "CLOSE_PROOF_HOLD_AT_WIRE"), \
        "ok=%r status=%r calls=%r rows=%r" % (ok, status, ex.calls,
                                              [(r.get("status"), r.get("terminal_state")) for r in rows])


def toctou_pre_send_mode_off_gives_zero_calls_and_terminalises_the_row():
    """TOCTOU, mode half: pre_send flips the global send mode to OFF while the lease is KEPT. ZERO exchange
    calls, and the pending_send row is terminalised (MASTER_REAL_ORDERS_OFF), not left pending."""
    led, ex, net, gw, it = _ceiling_fixture(7.0)
    real = gw._place_order
    mode = ["ON"]

    def off_then_send(exchange, sdk_coin, is_buy, size, limit_px, tif, reduce_only, timing=None,
                      started_key="", cloid=None, bypass_rate_limit_cooldown=False, pre_send=None,
                      intent=None, path="", **kw):
        def _off():
            aid = pre_send()
            mode[0] = "OFF"
            return aid
        return real(exchange, sdk_coin, is_buy, size, limit_px, tif, reduce_only, timing, started_key,
                    cloid=cloid, bypass_rate_limit_cooldown=bypass_rate_limit_cooldown,
                    pre_send=_off, intent=intent, path=path, **kw)

    gw.cfg.send_mode_now = lambda: mode[0]
    gw._place_order = off_then_send
    ok, status = gw.send_if_allowed(it)
    rows = send_rows("ceil-7.0-f")
    return (not ok and not ex.calls and len(rows) == 2
            and rows[0].get("status") == "pending_send"
            and rows[-1].get("status") == "BLOCKED_AT_PLACE_ORDER"
            and rows[-1].get("terminal_state") == "BLOCKED_AT_PLACE_ORDER"
            and "MASTER_REAL_ORDERS_OFF" in str(rows[-1].get("error") or "")), \
        "ok=%r status=%r calls=%r rows=%r" % (ok, status, ex.calls,
                                              [(r.get("status"), r.get("error")) for r in rows])


def ceil_excess_above_the_cap_is_blocked_close_untouched():
    """(b)+(d) The excess is an ENTRY: when the global cap leaves no allowance the increase is blocked (no second
    wire call) and the close is unaffected. max_order_notional is NOT the gate: setting it tiny changes nothing."""
    led, ex, net, gw, it = _ceiling_fixture(20.0, fixed_notional=500.0)
    gw.cfg.max_total_exposure = lambda: 0.5
    gw.cfg.max_order_notional = lambda: 0.01
    ok, status = gw.send_if_allowed(it)
    return (ok and len(ex.calls) == 1 and abs(ex.calls[0]["size"] - 10.0) < 1e-9
            and ex.calls[0]["reduce_only"] is True), \
        "ok=%r status=%r calls=%r (want only the close; the capped excess sends nothing)" % (ok, status, ex.calls)


def early_return_unowned_lease_never_calls_pre_send():
    """EARLY RETURN: when the lease is ALREADY unowned at entry, the write-ahead hook is never invoked (count the
    calls) and NO pending_send row is written: nothing is attempted, so nothing is terminalised."""
    led, ex, net, gw, it = _ceiling_fixture(5.0)
    attempts = []
    gw._begin_pending_send = lambda *a, **k: (attempts.append(1) or "should-never-be-written")
    saved = c._GLOBAL_INSTANCE_LOCK_OWNED
    try:
        c._GLOBAL_INSTANCE_LOCK_OWNED = False   # unowned at ENTRY, before any pending row could exist
        ok, status = gw.send_if_allowed(it)
    finally:
        c._GLOBAL_INSTANCE_LOCK_OWNED = saved
    rows = send_rows("ceil-5.0-f")
    return (not ok and not ex.calls and attempts == [] and rows == []), \
        "ok=%r status=%r sends=%r pre_send_calls=%d rows=%r" % (ok, status, ex.calls, len(attempts), rows)


def _ceil_close_oid(ex, index=0):
    """The exchange order id of the close leg's wire call, as the fake exchange returned it (oid = call number)."""
    return str(index + 1 + int(getattr(ex, "oid_base", 0)))


def _ceiling_owed_rows(fid):
    return [r for r in recon_rows(fid) if str(r.get("terminal_state") or "").startswith("CEILING_EXCESS_OWED")]


def _record_owned_close_fill(gw, ex, size, call_index=0):
    """Make the FILL LEDGER carry the close leg's own exchange order id for ``size`` - the external fill that proves
    the close matched IN FULL. Only live_fills.csv is written; no order is placed. Each witness must use its OWN
    ``oid_base`` so the per-order owned-size index (keyed by exchange order id) cannot accumulate across witnesses."""
    gw._owned_fill_size("0")  # prime the incremental per-order owned-size index before the row lands
    c.append_csv(c.LIVE_FILLS_CSV, c.LIVE_FILL_FIELDS, {
        "created_at": c.utc_now_iso(), "created_at_ms": c.utc_now_ms(),
        "copy_fill_id": "cf-ceil-%d" % call_index, "intent_id": "ceil-ext", "leader_fill_id": "ceil-ext",
        "leader_wallet": A, "sleeve_id": "", "position_id": "", "coin": COIN, "side": "SELL",
        "fill_price": PX, "fill_size": size, "fill_notional": size * PX, "fee": 0, "source": "TEST",
        "exchange_hash": "h-ceil-%d" % call_index, "exchange_order_id": _ceil_close_oid(ex, call_index),
        "ledger_action": "UPDATED", "wallet_position_before": "", "wallet_position_after": "",
        "coin_net_after": "", "notes": "external close fill, matched in full",
    })


def ceil_clo_blocks_the_excess_and_the_close_still_sends():
    """CC1-B-SENDBACK2-2140(1): the excess leg is an ENTRY for EVERY mode gate. A wallet in CLO (close-only) must
    still get its CLOSE, and must NOT get a NEW non-reduce-only ENTRY as the excess. The close is matched in full
    first, so the MODE GATE is the one and only thing standing between the excess and the wire."""
    led, ex, net, gw, it = _ceiling_fixture(20.0, fixed_notional=500.0, fid="ceil-clo-f", oid_base=2000)
    _record_owned_close_fill(gw, ex, 10.0)
    gw.cfg.wallet_mode = lambda w: "CLO"
    ok, status = gw.send_if_allowed(it)
    close_calls = [x for x in ex.calls if x["reduce_only"] is True]
    entry_calls = [x for x in ex.calls if x["reduce_only"] is False]
    owed = _ceiling_owed_rows("ceil-clo-f")
    return (ok and len(close_calls) == 1 and abs(close_calls[0]["size"] - 10.0) < 1e-9
            and entry_calls == [] and len(owed) == 1
            and "CLO_BLOCKS_ENTRY" in str(owed[0].get("terminal_state") or "")), \
        "ok=%r status=%r calls=%r owed=%r" % (ok, status, ex.calls,
                                              [(r.get("terminal_state"), r.get("notes")) for r in owed])


def ceil_global_close_only_blocks_the_excess_and_the_close_still_sends():
    """CC1-B-SENDBACK2-2140(1): global CLOSE-only (send_mode CLOSE) blocks the excess ENTRY too. The close still sends."""
    led, ex, net, gw, it = _ceiling_fixture(20.0, fixed_notional=500.0, fid="ceil-gclo-f", oid_base=3000)
    _record_owned_close_fill(gw, ex, 10.0)
    gw.cfg.send_mode_now = lambda: "CLOSE"
    ok, status = gw.send_if_allowed(it)
    close_calls = [x for x in ex.calls if x["reduce_only"] is True]
    entry_calls = [x for x in ex.calls if x["reduce_only"] is False]
    owed = _ceiling_owed_rows("ceil-gclo-f")
    return (ok and len(close_calls) == 1 and abs(close_calls[0]["size"] - 10.0) < 1e-9
            and entry_calls == [] and len(owed) == 1
            and "ENTRY_BLOCKED_GLOBAL_CLOSE_ONLY" in str(owed[0].get("terminal_state") or "")), \
        "ok=%r status=%r calls=%r owed=%r" % (ok, status, ex.calls,
                                              [(r.get("terminal_state"), r.get("notes")) for r in owed])


def ceil_resting_close_leaves_the_excess_owed():
    """CC1-B-SENDBACK2-2140(3): a RESTING close proves nothing about a fill, so the excess is NOT sent - it is left
    OWED in the journal, named, with its size. Not lost, not sent on an unconfirmed ack."""
    led, ex, net, gw, it = _ceiling_fixture(20.0, fixed_notional=500.0, fid="ceil-rest-f", oid_base=4000)
    ex.replies = [{"status": "ok", "response": {"type": "order", "data": {"statuses": [{"resting": {"oid": 4242}}]}}}]
    ok, status = gw.send_if_allowed(it)
    entry_calls = [x for x in ex.calls if x["reduce_only"] is False]
    owed = _ceiling_owed_rows("ceil-rest-f")
    return (len(ex.calls) == 1 and entry_calls == [] and len(owed) == 1
            and "ORDER_RESTING" in str(owed[0].get("terminal_state") or "")
            and "owed_size=5.0" in str(owed[0].get("notes") or "")), \
        "ok=%r status=%r calls=%r owed=%r" % (ok, status, ex.calls,
                                              [(r.get("terminal_state"), r.get("notes")) for r in owed])


def ceil_partial_close_leaves_the_excess_owed():
    """CC1-B-SENDBACK2-2140(2)/(3): the close ack says filled, but the FILL LEDGER only matched 4 of the 10 units -
    the close is PARTIAL, so the excess is NOT sent and stays OWED."""
    led, ex, net, gw, it = _ceiling_fixture(20.0, fixed_notional=500.0, fid="ceil-part-f", oid_base=5000)
    _record_owned_close_fill(gw, ex, 4.0)
    ok, status = gw.send_if_allowed(it)
    entry_calls = [x for x in ex.calls if x["reduce_only"] is False]
    owed = _ceiling_owed_rows("ceil-part-f")
    return (len(ex.calls) == 1 and entry_calls == [] and len(owed) == 1
            and "CEILING_EXCESS_OWED_CLOSE_NOT_MATCHED_IN_FULL" == str(owed[0].get("terminal_state") or "")), \
        "ok=%r status=%r calls=%r owed=%r" % (ok, status, ex.calls,
                                              [(r.get("terminal_state"), r.get("notes")) for r in owed])


def ceil_unknown_close_leaves_the_excess_owed():
    """CC1-B-SENDBACK2-2140(3): an UNKNOWN close outcome (unparseable ack) never sends the excess; it is left OWED."""
    led, ex, net, gw, it = _ceiling_fixture(20.0, fixed_notional=500.0, fid="ceil-unk-f", oid_base=6000)
    ex.replies = [{"status": "ok", "response": {"type": "order", "data": {"statuses": [{"whatever": {}}]}}}]
    ok, status = gw.send_if_allowed(it)
    entry_calls = [x for x in ex.calls if x["reduce_only"] is False]
    owed = _ceiling_owed_rows("ceil-unk-f")
    return (len(ex.calls) == 1 and entry_calls == [] and len(owed) == 1
            and "ORDER_UNKNOWN" in str(owed[0].get("terminal_state") or "")), \
        "ok=%r status=%r calls=%r owed=%r" % (ok, status, ex.calls,
                                              [(r.get("terminal_state"), r.get("notes")) for r in owed])


def ceil_matched_close_then_the_excess_sends():
    """POSITIVE: the close leg is matched IN FULL by the fill ledger (its own exchange order id, 10 of 10), the net is
    re-read, the mode is re-checked ON - and ONLY THEN does the excess ENTRY go, on its own cloid, non-reduce-only."""
    led, ex, net, gw, it = _ceiling_fixture(20.0, fixed_notional=500.0, fid="ceil-ok-f", oid_base=7000)
    _record_owned_close_fill(gw, ex, 10.0)
    ok, status = gw.send_if_allowed(it)
    close_calls = [x for x in ex.calls if x["reduce_only"] is True]
    entry_calls = [x for x in ex.calls if x["reduce_only"] is False]
    owed = _ceiling_owed_rows("ceil-ok-f")
    return (ok and len(close_calls) == 1 and abs(close_calls[0]["size"] - 10.0) < 1e-9
            and len(entry_calls) == 1 and entry_calls[0]["size"] > 0
            and entry_calls[0]["is_buy"] is False and owed == []), \
        "ok=%r status=%r calls=%r owed=%r" % (ok, status, ex.calls,
                                              [(r.get("terminal_state")) for r in owed])


def main():
    started = time.perf_counter()
    witnesses = [
        ("W1_STALE_REPLAY_ON_FLAT_SLEEVE_IS_A_NAMED_NO_SEND_WITH_ONE_DURABLE_ROW", w1),
        ("W2_NETTED_OPPOSITE_LEADER_REDUCTION_STILL_SENDS_GROSS_RISES", w2),
        ("W3A_LIVE_SLEEVE_CLOSE_SENDS_REDUCE_ONLY", w3a),
        ("W3B_USER_RESIDUAL_ON_THE_COIN_ENGINE_CLOSE_OF_ITS_OWN_SLEEVE_STILL_SENDS", w3b_user_residual),
        ("W4A_DUST_WHOLE_POSITION_CLOSE_SENDS_EXACT_FULL_CLOSE", w4a_whole_position),
        ("W4B_SUBMIN_REMAINDER_WITH_RESIDUAL_IS_HELD_NOT_SENT_AS_A_PARTIAL", w4b_submin_remainder_is_held_not_sent),
        ("W4C_HELD_REMAINDER_RESOLVED_BY_WHOLE_POSITION_CLOSE_WHEN_ACCOUNT_WOULD_GO_FLAT",
         w4c_resolved_by_whole_position_close_when_account_would_go_flat),
        ("W4D_NO_ENGINE_DUST_REMAINS_WHEN_THE_EXCHANGE_IS_FLAT", w4d_no_engine_dust_remains_when_exchange_is_flat),
        ("W5_OLDER_TERMINAL_FILL_ID_DOES_NOT_BLOCK_A_FRESH_EXIT_ON_A_LIVE_SLEEVE", w5),
        ("W6A_UNREADABLE_EXCHANGE_NEVER_CLAIMS_FLAT", w6a_unreadable_exchange_never_claims_flat),
        ("W6B_R1_WRONG_ACCOUNT_REQUIRES_DURABLE_HOLD_NO_SDK",
         w6b_wrong_account_flat_read_never_claims_flat_and_close_is_sent),
        ("W7_HELD_DUST_ON_THE_SAME_FILL_ID_IS_NOT_CONSUMED", w7_held_same_fill_is_not_consumed),
        ("W8_ABSENT_KEY_IN_A_PARTIAL_LEDGER_IS_UNKNOWN_NO_FABRICATED_SLEEVE", w8_absent_key_in_a_partial_ledger_is_unknown),
        ("W9_TWO_SIMULTANEOUS_STALE_REPLAYS_PRODUCE_EXACTLY_ONE_NO_SEND", w9),
        ("RESTART_CONSUMED_EXIT_INTENT_AGAINST_FLAT_LEDGER_AND_FLAT_EXCHANGE_OPENS_NOTHING",
         restart_consumed_exit_never_opens_a_position),
        ("CE1_CS_I2_I3_OWNED_HALF_CLOSES_HALF_FOREIGN_4_5_NUMERIC",
         ce1_stale_owned_does_not_eat_foreign),
        ("CE2_R1_I22_WRONG_MASTER_FOREIGN_5_NUMERIC_AND_OWED_RED",
         ce2_bad_master_does_not_eat_foreign),
        ("CE1B_REFUSED_CLOSE_OWED_RED_FOREIGN_RESIDUAL_UNTOUCHED",
         ce1b_refused_close_owes_a_red_and_leaves_the_foreign_residual_untouched),
        ("R81_SHARE_OF_LEADER_POSITION_1000_CLOSES_1", r81_share_of_roleader_position),
        ("R81_MISSING_START_POSITION_IS_FULL_SLEEVE", r81_missing_start_is_full_sleeve),
        ("R81_WHOLE_LEADER_CLOSE_IS_FULL_SLEEVE", r81_whole_leader_close_is_full_sleeve),
        ("R81_HALF_LEADER_CLOSE_IS_HALF_SLEEVE", r81_half_leader_close_is_half_sleeve),
        ("R81_SIGN_FILL_OPPOSING_START_IS_CAUGHT_FLIP_THROUGH_ZERO", r81_sign_flip_through_zero),
        ("R81_SIGN_ADD_TO_SHORT_NEVER_REACHES_THE_WIRE", r81_sign_add_to_short_never_reaches_the_wire),
        ("R81_SIGN_CHAINED_CATCHUP_PARTIAL_CLOSES", r81_sign_chained_catchup),
        ("R81_SIGN_ROUNDING_AT_SIZE_DECIMALS", r81_sign_rounding_at_size_decimals),
        ("R81_SIGN_SUBMINIMUM_RESIDUAL_IS_WHOLE_CLOSE", r81_sign_subminimum_residual_is_whole_close),
        ("EVENT_LOSS_CS_I2_COIN_NET_EQUALITY_NOT_FILL_PROOF",
         missing_fill_equal_coin_net_is_not_proof),
        ("RESTART_I05_I06_UNRESOLVED_RED_SURVIVES",
         unresolved_owed_survives_restart),
        ("CEILING_W2B_200PCT_SLEEVE_CLOSE_PLUS_EXCESS_CLIPPED_TO_ENTRY_SIZE",
         ceil_w2b_excess_is_clipped_to_entry_size),
        ("CEILING_PURE_CLOSE_AT_OR_UNDER_SLEEVE_NEVER_REDUCED_BY_ANY_CAP",
         ceil_pure_close_never_reduced_by_any_cap),
        ("CEILING_EXCESS_WITH_UNKNOWN_ENTRY_SIZING_LOUD_FAULT_CLOSE_STILL_SENDS",
         ceil_unknown_entry_sizing_is_a_loud_fault_and_the_close_still_sends),
        ("CEILING_EXCESS_ABOVE_CAP_BLOCKED_CLOSE_UNTOUCHED",
         ceil_excess_above_the_cap_is_blocked_close_untouched),
        ("CEILING_CLO_BLOCKS_THE_EXCESS_THE_CLOSE_STILL_SENDS",
         ceil_clo_blocks_the_excess_and_the_close_still_sends),
        ("CEILING_GLOBAL_CLOSE_ONLY_BLOCKS_THE_EXCESS_THE_CLOSE_STILL_SENDS",
         ceil_global_close_only_blocks_the_excess_and_the_close_still_sends),
        ("CEILING_RESTING_CLOSE_LEAVES_THE_EXCESS_OWED",
         ceil_resting_close_leaves_the_excess_owed),
        ("CEILING_PARTIAL_CLOSE_LEAVES_THE_EXCESS_OWED",
         ceil_partial_close_leaves_the_excess_owed),
        ("CEILING_UNKNOWN_CLOSE_LEAVES_THE_EXCESS_OWED",
         ceil_unknown_close_leaves_the_excess_owed),
        ("CEILING_CLOSE_MATCHED_IN_FULL_THEN_THE_EXCESS_SENDS",
         ceil_matched_close_then_the_excess_sends),
        ("TOCTOU_PRE_SEND_LEDGER_MOVES_ZERO_CALLS_ROW_TERMINALISED",
         toctou_pre_send_ledger_moves_gives_zero_calls_and_terminalises_the_row),
        ("TOCTOU_PRE_SEND_MODE_OFF_ZERO_CALLS_ROW_TERMINALISED",
         toctou_pre_send_mode_off_gives_zero_calls_and_terminalises_the_row),
        ("EARLY_RETURN_UNOWNED_LEASE_AT_ENTRY_NEVER_CALLS_PRE_SEND",
         early_return_unowned_lease_never_calls_pre_send),
        *[("DOOR_%d_CS_I1_I2_I3_FINAL_PHYSICAL_ENVELOPE" % k,
           (lambda k=k: bypass_door(k))) for k in range(1, 8)],
    ]
    for nm, fn in witnesses:
        case(nm, fn)
    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d RUNTIME_SEC=%.3f" % (len(RESULTS), len(failed), time.perf_counter() - started))
    if failed:
        print("FAILED: " + ", ".join(failed))
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
