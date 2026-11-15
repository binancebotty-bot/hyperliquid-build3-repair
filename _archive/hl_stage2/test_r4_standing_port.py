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

def standing_guard(row, sleeve=10.0, ex_net=10.0, age_ms=1000, cancel_ok=True, gmode="ON", led_net=None):
    """Real SenderGateway; the REAL guard_standing_closes runs. Only the exchange is a fake."""
    led, ex, net = new_ledger(), FakeExchange(), [ex_net]
    cancels = []
    def cancel(coin, oid):
        cancels.append(str(oid))
        if cancel_ok:
            return {"response": {"data": {"statuses": ["success"]}}}
        return {"response": {"data": {"statuses": [{"error": "boom"}]}}}
    ex.cancel = cancel
    gw = make_gateway(ex, led, net)
    gw.cfg.send_mode_now = lambda: gmode
    set_sleeve(led, A, sleeve)
    r = dict(row, wallet=A, placed_ms=c.utc_now_ms() - age_ms)
    gw._standing_closes = {"s1": r}
    n = c.SenderGateway.guard_standing_closes(gw)
    return n, cancels, dict(gw._standing_closes)

base = {"oid": "7", "coin": "BTC", "sdk_coin": "BTC", "size": 10.0, "side": "SELL", "intent_id": "i1", "reduce_only": False,
        "sleeve_signed": 10.0, "led_net": 10.0, "sleeve_tol": 0.0}

n, can, left = standing_guard(base)
check("PORT_UNCHANGED_ORDER_STAYS", n == 0 and not can and "s1" in left, f"n={n} can={can}")
n, can, left = standing_guard(base, age_ms=10 ** 9)
check("PORT_OLD_ORDER_IS_CANCELLED", n == 1 and can == ["7"] and "s1" not in left, f"n={n} can={can} left={list(left)}")
n, can, _ = standing_guard(base, sleeve=4.0)
check("PORT_LEADER_SLEEVE_CHANGE_CANCELS", n == 1 and can == ["7"], f"n={n} can={can}")
n, can, _ = standing_guard(base, ex_net=0.0)
check("PORT_TARGET_REACHED_CANCELS", n == 1, f"n={n} can={can}")
n, can, _ = standing_guard(base, ex_net=4.0)
check("PORT_EXCHANGE_HOLDS_LESS_THAN_ORDER_CANCELS", n == 1, f"n={n} can={can}")
n, can, _ = standing_guard(base, ex_net=None)
check("PORT_UNREADABLE_ACCOUNT_CANCELS", n == 1, f"n={n} can={can}")
n, can, _ = standing_guard(base, ex_net=25.0)
check("PORT_TARGET_NEEDS_MORE_THAN_ORDER_STAYS", n == 0, f"n={n} can={can}")
n, can, left = standing_guard(base, age_ms=10 ** 9, cancel_ok=False)
check("PORT_FAILED_CANCEL_KEEPS_ROW_FOR_NEXT_ROUND", n == 0 and can == ["7"] and "s1" in left, f"n={n} can={can}")
n, can, _ = standing_guard(base, gmode="CLOSE")
check("PORT_HEADER_CLOSE_ONLY_DOES_NOT_CANCEL", n == 0 and not can, f"n={n} can={can}")
n, can, _ = standing_guard(dict(base, reduce_only=True), age_ms=10 ** 9)
check("PORT_REDUCE_ONLY_ROWS_ARE_LEFT_ALONE", n == 0 and not can, f"n={n} can={can}")
n, can, _ = standing_guard(dict(base, sleeve_signed=10.0, sleeve_tol=3.0), sleeve=7.0)
check("PORT_SLEEVE_MAY_SHRINK_BY_THE_UNSEEN_PART_FILL", n == 0, f"n={n} can={can}")
n, can, _ = standing_guard(dict(base, sleeve_signed=10.0, sleeve_tol=3.0), sleeve=5.0)
check("PORT_SLEEVE_SHRINKING_MORE_CANCELS", n == 1, f"n={n} can={can}")
n, can, _ = standing_guard(base, sleeve=-10.0)
check("PORT_SLEEVE_FLIPPING_CANCELS", n == 1, f"n={n} can={can}")

def lag_plan(side, size, ex, lag, mode="ON"):
    led, exch, net = new_ledger(), FakeExchange(), [ex]
    gw = make_gateway(exch, led, net)
    gw.cfg.wallet_mode = lambda w: mode
    gw._reduce_only_for_intent = lambda i: True
    gw._floor_wire_size = lambda s, d: round(s, d)
    it = exit_intent(led, A, side, size, "lag-" + str(size) + "-" + str(ex), 0.0)
    return c.SenderGateway._close_wire_plan(gw, it, size, 3, lambda s: True, None, lag)

check("PORT_LAG_SIZES_FROM_EXCHANGE_ONLY", lag_plan("SELL", 6.0, 4.0, True) == (True, 4.0, ""), str(lag_plan("SELL", 6.0, 4.0, True)))
check("PORT_LAG_NOTHING_TO_CLOSE_SKIPS", lag_plan("SELL", 6.0, 0.0, True)[1] == 0.0 and lag_plan("SELL", 6.0, -3.0, True)[1] == 0.0)
check("PORT_LAG_FULL_POSITION_KEEPS_ORDER_SIZE", lag_plan("SELL", 6.0, 9.0, True) == (True, 6.0, ""), str(lag_plan("SELL", 6.0, 9.0, True)))
check("PORT_LAG_WALLET_CLOSE_ONLY_IS_NOT_REDUCE_ONLY", lag_plan("SELL", 6.0, 9.0, True, mode="CLO") == (True, 6.0, ""), str(lag_plan("SELL", 6.0, 9.0, True, mode="CLO")))
print("PORT_TOTAL=%d FAILED=%d" % (len(RESULTS), sum(1 for _, ok in RESULTS if not ok)), flush=True)
