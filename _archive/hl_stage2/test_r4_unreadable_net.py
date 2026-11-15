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

def unreadable_net_owned_exit_is_reduce_only():
    """Exchange net unreadable; we OWN 10 and the leader reduces 10. The close must still be sent reduce_only
    (a reduce-only order cannot open a new position). Refusing or sending non-reduce-only is the regression."""
    led, ex, net = new_ledger(), FakeExchange(), [None]
    gw = make_gateway(ex, led, net)
    set_sleeve(led, A, 10.0)
    it = exit_intent(led, A, "SELL", 10.0, "unreadable-owned-1", 10.0)
    ok, status = gw.send_if_allowed(it)
    check("UNREADABLE_NET_OWNED_EXIT_IS_SENT_REDUCE_ONLY",
          ok and len(ex.calls) == 1 and ex.calls[0]["reduce_only"] is True,
          f"ok={ok} status={status} calls={ex.calls}")

unreadable_net_owned_exit_is_reduce_only()
print("UNREADABLE_TOTAL=%d FAILED=%d" % (len(RESULTS), sum(1 for _, ok in RESULTS if not ok)), flush=True)
